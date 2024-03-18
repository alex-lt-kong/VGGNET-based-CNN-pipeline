#include "model_utils.h"

#include <cstdlib>
#include <cxxopts.hpp>
#include <nlohmann/json.hpp>
#include <opencv2/core.hpp>
#include <opencv2/core/cuda.hpp>
#include <opencv2/core/mat.hpp>
#include <opencv2/core/types.hpp>
#include <opencv2/cudaarithm.hpp>
#include <opencv2/cudacodec.hpp>
#include <opencv2/cudaimgproc.hpp>
#include <opencv2/cudawarping.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/imgproc/imgproc.hpp>

#include <filesystem>
#include <iostream>
#include <signal.h>
#include <sstream>
#include <stdio.h>
#include <thread>

using namespace cv;
using namespace std;

string torch_script_serialization;

using json = nlohmann::json;

static volatile sig_atomic_t e_flag = 0;

static void signal_handler(int signum) {
  char msg[] = "Signal [  ] caught\n";
  msg[8] = '0' + (char)(signum / 10);
  msg[9] = '0' + (char)(signum % 10);
  (void)write(STDIN_FILENO, msg, strlen(msg));
  e_flag = 1;
}

torch::Tensor get_tensor_from_mat_vector(vector<Mat> &images) {
  std::vector<torch::Tensor> tensor_vec;

  for (const auto &image : images) {
    tensor_vec.push_back(cv_mat_to_tensor(image));
  }
  return torch::stack(tensor_vec);
}

inline void install_signal_handler() {
  // This design canNOT handle more than 99 signal types
  if (_NSIG > 99) {
    fprintf(stderr, "signal_handler() can't handle more than 99 signals\n");
    abort();
  }
  struct sigaction act;
  // Initialize the signal set to empty, similar to memset(0)
  if (sigemptyset(&act.sa_mask) == -1) {
    perror("sigemptyset()");
    abort();
  }
  act.sa_handler = signal_handler;
  /* SA_RESETHAND means we want our signal_handler() to intercept the signal
  once. If a signal is sent twice, the default signal handler will be used
  again. `man sigaction` describes more possible sa_flags. */
  act.sa_flags = SA_RESETHAND;
  // act.sa_flags = 0;
  if (sigaction(SIGINT, &act, 0) == -1 || sigaction(SIGTERM, &act, 0) == -1) {
    perror("sigaction()");
    abort();
  }
}

int main(int argc, const char *argv[]) {
  install_signal_handler();
  cxxopts::Options options(argv[0], "Video classifier");
  string configPath, srcVideoPath, dstVideoPath;
  int numClasses = 2;
  // clang-format off
  options.add_options()
    ("h,help", "Print help message")
    ("s,src-video-path", "Source video path", cxxopts::value<string>()->default_value(srcVideoPath))
    ("d,dst-video-path", "Destination video path", cxxopts::value<string>()->default_value(dstVideoPath))
    ("n,num-classes", "Number of classes of output", cxxopts::value<int>()->default_value(to_string(numClasses)))
    ("c,config-path", "JSON configuration file path",  cxxopts::value<string>()->default_value(configPath));
  // clang-format on
  auto result = options.parse(argc, argv);
  if (result.count("help") || !result.count("config-path") ||
      !result.count("src-video-path") ||
      !result.count("dst-video-path") //||      !result.count("num-classes")
  ) {
    cout << "getBuildInformation():\n" << getBuildInformation() << endl;
    cout << options.help() << "\n";
    return 0;
  }
  configPath = result["config-path"].as<string>();
  srcVideoPath = result["src-video-path"].as<string>();
  dstVideoPath = result["dst-video-path"].as<string>();
  numClasses = result["num-classes"].as<int>();

  // config_path = (parentPath / "config.json").string();
  ifstream f(configPath);

  json settings = json::parse(f);

  vector<string> model_ids = settings.value(
      "/inference/initial_model_ids"_json_pointer, vector<string>{"0"});
  torch_script_serialization = settings.value(
      "/model/torch_script_serialization"_json_pointer, string(""));
  vector<torch::jit::script::Module> v16mms = load_models(model_ids);

  cuda::GpuMat dFrame;
  vector<Mat> hFrames;

  Ptr<cudacodec::VideoReader> dReader =
      cudacodec::createVideoReader(srcVideoPath);

  if (!dReader->nextFrame(dFrame)) {
    cerr << "Failed to read frame from source\n";
    return EXIT_FAILURE;
  }
  Ptr<cudacodec::VideoWriter> dWriter = cudacodec::createVideoWriter(
      string(dstVideoPath), dFrame.size(), cudacodec::Codec::H264, 45.0,
      cudacodec::ColorFormat::BGR);
  dReader.release();
  dReader = cudacodec::createVideoReader(srcVideoPath);
  dReader->set(cv::cudacodec::ColorFormat::BGR);
  size_t frameCount = 0;
  size_t batchSize = 8;
  while (!e_flag) {
    if (!dReader->nextFrame(dFrame)) {
      cerr << "dReader->nextFrame(dFrame) is False" << endl;
      break;
    }
    if (dFrame.empty()) {
      break;
    } else if (frameCount % 100 == 0) {
      cout << "frameCount: " << frameCount << ", size(): " << dFrame.size()
           << ", channels(): " << dFrame.channels() << endl;
    }
    Mat hFrame;
    dFrame.download(hFrame);
    ++frameCount;
    hFrames.push_back(hFrame);

    if (hFrames.size() < batchSize)
      continue;
    auto imgs_tensor = get_tensor_from_mat_vector(hFrames);
    vector<torch::jit::IValue> input(1);
    input[0] = imgs_tensor.to(torch::kCUDA);
    // imgs_tensor.sizes()[0] stores number of images
    at::Tensor avg_output = torch::zeros({imgs_tensor.sizes()[0], numClasses});
    avg_output = avg_output.to(torch::kCUDA);
    vector<at::Tensor> raw_outputs(v16mms.size());
    for (size_t i = 0; i < v16mms.size(); ++i) {
      raw_outputs[i] = v16mms[i].forward(input).toTensor();
      avg_output += raw_outputs[i];
    }
    at::Tensor y_preds = torch::argmax(avg_output, 1);
    // cout << tensor_to_string_like_pytorch(y_pred, 0, batchSize) << endl;
    for (size_t i = 0; i < hFrames.size(); ++i) {
      float fontScale = 5;
      int y_pred = y_preds[i].item<int>();
      Point cords = Point(16, 256);
      Scalar color;

      if (y_pred == 0)
        color = Scalar(0, 0, 255);
      else if (y_pred == 2)
        color = Scalar(0, 255, 0);
      else
        color = Scalar(255, 255, 255);

      putText(hFrames[i], to_string(y_pred), cords, FONT_HERSHEY_DUPLEX,
              fontScale, Scalar(0, 0, 0), 4 * fontScale, LINE_8, false);
      putText(hFrames[i], to_string(y_pred), cords, FONT_HERSHEY_DUPLEX,
              fontScale, color, fontScale, LINE_8, false);

      dFrame.upload(hFrames[i]);
      dWriter->write(dFrame);
    }
    hFrames.clear();
  }
  dWriter->release();
  cout << "dWriter->release()ed" << endl;
  dReader.release();
  cout << "dReader->release()ed" << endl;
  return 0;
}
