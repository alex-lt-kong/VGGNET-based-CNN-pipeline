from sklearn import metrics
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
from torch.utils.data import random_split
from typing import Any, Dict, List, Tuple, Optional

import argparse
import datetime as dt
import helper
import logging
import itertools
import json
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import random
import shutil
import sys
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torch.cuda
import time


curr_dir = os.path.dirname(os.path.abspath(__file__))
device: torch.device
config: Dict[str, Any]


class VGG16MinusMinus(nn.Module):
    dropout = 0.66
    num_classes = -1

    def __init__(self, num_classes: int, target_image_size: Tuple[int, int]) -> None:
        self.num_classes = num_classes
        self.target_image_size = target_image_size

        super(VGG16MinusMinus, self).__init__()
        # self.layer1 = nn.Sequential(
        #     nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1),
        #     nn.BatchNorm2d(64),
        #     nn.ReLU())
        self.layer2 = nn.Sequential(
            nn.Conv2d(3, 8, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(8),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2))
        self.layer3 = nn.Sequential(
            nn.Conv2d(8, 12, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(12),
            nn.ReLU())
        # self.layer4 = nn.Sequential(
        #    nn.Conv2d(128, 128, kernel_size=3, stride=1, padding=1),
        #    nn.BatchNorm2d(128),
        #    nn.ReLU(),
        #    nn.MaxPool2d(kernel_size=2, stride=2))
        self.layer5 = nn.Sequential(
            nn.Conv2d(12, 16, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2))
        # self.layer6 = nn.Sequential(
        #    nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1),
        #    nn.BatchNorm2d(256),
        #    nn.ReLU())
        self.layer7 = nn.Sequential(
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2))
        # self.layer8 = nn.Sequential(
        #     nn.Conv2d(256, 512, kernel_size=3, stride=1, padding=1),
        #     nn.BatchNorm2d(512),
        #     nn.ReLU())
        # self.layer9 = nn.Sequential(
        #    nn.Conv2d(512, 512, kernel_size=3, stride=1, padding=1),
        #    nn.BatchNorm2d(512),
        #    nn.ReLU())
        self.layer10 = nn.Sequential(
            nn.Conv2d(32, 48, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(48),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2))
        # self.layer11 = nn.Sequential(
        #     nn.Conv2d(512, 512, kernel_size=3, stride=1, padding=1),
        #     nn.BatchNorm2d(512),
        #     nn.ReLU())
        self.layer12 = nn.Sequential(
             nn.Conv2d(48, 64, kernel_size=3, stride=1, padding=1),
             nn.BatchNorm2d(64),
             nn.ReLU(),
             nn.MaxPool2d(kernel_size=2, stride=2))
        self.layer13 = nn.Sequential(
            nn.Conv2d(64, 256, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2))
        self.fc = nn.Sequential(
            nn.Linear(
                int(self.target_image_size[0] / 64) *
                int(self.target_image_size[1] / 64) * 256,
                int(4096 / 38)
            ),
            nn.Dropout(self.dropout),
            nn.ReLU())
        self.fc1 = nn.Sequential(
            nn.Linear(int(4096 / 38), int(4096 / 38)),
            nn.Dropout(self.dropout),
            nn.ReLU())
        self.fc2 = nn.Sequential(
            nn.Linear(int(4096 / 38), num_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        # x = self.layer4(x)
        x = self.layer5(x)
        # x = self.layer6(x)
        x = self.layer7(x)
        # x = self.layer8(x)
        # x = self.layer9(x)
        x = self.layer10(x)
        # x = self.layer11(x)
        x = self.layer12(x)
        x = self.layer13(x)
        x = x.reshape(x.size(0), -1)
        x = self.fc(x)
        x = self.fc1(x)
        x = self.fc2(x)
        return x


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True

    # Prevents PyTorch from using the cudnn auto-tuner to find the fastest
    # convolution algorithms, which can result in non-deterministic behavior.
    torch.backends.cudnn.benchmark = False


def get_data_loaders(data_path: str,
                     random_seed: int = 0) -> Tuple[DataLoader, DataLoader, DataLoader]:

    class TransformedSubset(torch.utils.data.Subset):

        cached_data: List[Any] = []

        def __init__(
            self, subset: torch.utils.data.Subset,
            dataset_name: str,
            transform: Optional[torchvision.transforms.Compose] = None
        ) -> None:
            assert isinstance(subset, torch.utils.data.Subset)
            self.subset = subset
            self.dataset_name = dataset_name
            self.transform = transform
            # x, y = self.subset[i]
            # if transform:
                # torch.save(
                #     transform(self.subset[i][0]),
                #     f'/tmp/usb-hdd/{self.dataset_name}_sample_{i:05d}.pt'
                # )
                # self.cached_data.append(transform(self.subset[i][0]))

        def __getitem__(self, index: int) -> Tuple[Any, Any]:
            x, y = self.subset[index]
            # assert isinstance(x, Image.Image)
            if self.transform:
                x = self.transform(x)
            # t = torch.load(
            #     f'/tmp/usb-hdd/{self.dataset_name}_sample_{index:05d}.pt'
            # )
            # t = self.cached_data[index]
            assert isinstance(x, torch.Tensor)
            return x, self.subset[index][1]

        def __len__(self) -> int:
            return len(self.subset)

    dataset = ImageFolder(root=data_path, transform=None)
    test_split_ratio = 0.2
    train_size = int((1 - test_split_ratio) * len(dataset))
    test_size = len(dataset) - train_size

    train_dataset, test_dataset = random_split(
        dataset, [train_size, test_size],
        generator=torch.Generator().manual_seed(random_seed))

    train_dataset_for_eval = train_dataset
    batch_size = 64
    shuffle = True
    # Apply the respective transformations to each subset
    train_dataset = TransformedSubset(
        train_dataset, 'train', transform=helper.train_transforms
    )
    train_dataset_for_eval = TransformedSubset(
        train_dataset_for_eval, 'train-for-eval', transform=helper.test_transforms
    )
    test_dataset = TransformedSubset(test_dataset, 'test', transform=helper.test_transforms)

    train_loader = DataLoader(train_dataset,
                              batch_size=batch_size, shuffle=shuffle)
    train_loader_for_eval = DataLoader(train_dataset_for_eval,
                                       batch_size=batch_size, shuffle=shuffle)
    test_loader = DataLoader(test_dataset,
                             batch_size=batch_size, shuffle=shuffle)
    return (train_loader, train_loader_for_eval, test_loader)


def write_metrics_to_csv(filename: str, metrics_dict: Dict[str, float]) -> None:

    csv_dir = os.path.join(config['model']['diagnostics_dir'], 'training')
    if not os.path.isdir(csv_dir):
        os.makedirs(csv_dir)
    csv_path = os.path.join(csv_dir, filename)
    if os.path.isfile(csv_path):
        df = pd.read_csv(csv_path)
    else:        
        df = pd.DataFrame()
    # logging.info(f'Appending:\n{metrics_dict}\n--- to ---\n{df}')
    df = df.append(metrics_dict, ignore_index=True)
    df.to_csv(csv_path, index=False)


def evalute_model_classification(
    model: nn.Module, num_classes: int, data_loader: DataLoader,
    ds_name: str, step: int
) -> None:
    # initialize the number of correct predictions, total number of samples,
    # and true positives, false positives, and false negatives for each class
    num_correct = 0
    total_samples = 0
    true_positives = np.zeros(num_classes)
    false_positives = np.zeros(num_classes)
    false_negatives = np.zeros(num_classes)

    y_trues_total = []
    y_preds_total = []
    # Disabling gradient calculation is useful for inference, when you are
    # sure that you will not call Tensor.backward(). It will reduce memory
    # consumption for computations that would otherwise have requires_grad=True.
    torch.set_grad_enabled(False)
    for batch_idx, (images, y_trues) in enumerate(
        itertools.islice(data_loader, random.randint(0, step-1), None, step)
    ):
        # logging.info(batch_idx)
        images, y_trues = images.to(device), y_trues.to(device)
        # forward pass
        output = model(images)
        # compute the predicted labels
        y_preds = torch.argmax(output, dim=1)

        y_trues_total.extend(y_trues.tolist())
        y_preds_total.extend(y_preds.tolist())
        # update the number of correct predictions, total number of
        # samples, and true positives, false positives, and false
        # negatives for each class
        num_correct += (y_preds == y_trues).sum().item()
        total_samples += y_trues.size(0)
        for i in range(y_trues.size(0)):
            if y_preds[i] == y_trues[i]:
                true_positives[y_trues[i]] += 1
            else:
                false_positives[y_preds[i]] += 1
                false_negatives[y_trues[i]] += 1
        # logging.info('Iter done')
    torch.set_grad_enabled(True)
    # compute the accuracy
    # accuracy = num_correct / total_samples
    # logging.info('Accuracy: {:.2f}%'.format(accuracy * 100))
    # compute the precision, recall, and f-score for each class
    precision = np.zeros(num_classes)
    recall = np.zeros(num_classes)
    fscore = np.zeros(num_classes)
    for i in range(num_classes):
        precision[i] = true_positives[i] / \
            (true_positives[i] + false_positives[i])
        recall[i] = true_positives[i] / \
            (true_positives[i] + false_negatives[i])
        beta = 1  # set beta to 1 for f1-score
        fscore[i] = (1 + beta**2) * (precision[i] * recall[i]
                                     ) / (beta**2 * precision[i] + recall[i])

    logging.info(f'Metrics from dataset: {ds_name} '
                 f'(1 of every {step} samples evaluted)')

    metrics_dict = {}
    logging.info('Class\tPrecision\tRecall\t\tF-Score')
    for i in range(num_classes):
        metrics_dict[f'{i}_precision'] = precision[i]
        metrics_dict[f'{i}_recall'] = recall[i]
        metrics_dict[f'{i}_fscore'] = fscore[i]
        logging.info('{}    \t{:.2f}%\t\t{:.2f}%\t\t{:.2f}%'.format(
            i, precision[i] * 100, recall[i] * 100, fscore[i] * 100))
    write_metrics_to_csv(f'{ds_name}.csv', metrics_dict)

    generate_curves(ds_name)
    generate_curves(ds_name, 4)
    generate_curves(ds_name, 16)
    generate_curves(ds_name, 64)

    cm = metrics.confusion_matrix(y_trues_total, y_preds_total)
    logging.info(f'Confusion matrix (true-by-pred):\n{cm}')


def save_params(m: nn.Module, model_id: str) -> None:
    model_params_path = config['model']['parameters'].replace(
        r'{id}', model_id
    )
    if os.path.exists(model_params_path):
        dst_path = model_params_path + '.bak'
        shutil.move(model_params_path, dst_path)
    torch.save(m.state_dict(), model_params_path)
    logging.info(f'Model weights saved to [{model_params_path}]')


def save_ts_model(m: nn.Module, model_id: str) -> None:
    logging.info('Serializing model to Torch Script file')
    ts_serialization_path = config['model'][
        'torch_script_serialization'
    ].replace(r'{id}', model_id)
    if os.path.exists(ts_serialization_path):
        dst_path = ts_serialization_path + '.bak'
        shutil.move(ts_serialization_path, dst_path)
    m_ts = torch.jit.script(m)
    logging.info('Torch Script model created')
    m_ts.save(ts_serialization_path)
    logging.info(f'Torch Script model saved to [{ts_serialization_path}]')


def save_transformed_samples(dataloader: DataLoader,
                             save_dir: str, num_samples: int) -> None:
    logging.info(f'Saving transformed samples to {save_dir}')
    from torchvision.utils import save_image
    if os.path.exists(save_dir):
        shutil.rmtree(save_dir)
    os.makedirs(save_dir)
    dataset_size = len(dataloader.dataset)  # type: ignore
    logging.info(
        f"{dataset_size} images are in this dataset and we sample {num_samples} from it."
    )
    for i in range(num_samples):
        image_dst_path = f"{save_dir}/sample_{i}.jpg"
        sample_idx = random.randint(0, dataset_size - 1)
        save_image(
            dataloader.dataset[sample_idx][0],
            # dataloader.dataset[sample_idx][1] is label
            image_dst_path
        )


def train(
    load_parameters: bool, model_id: str, num_classes: int,
    target_image_size: Tuple[int, int], lr: float = 0.001,
    epochs: int = 10
) -> nn.Module:

    v16mm = VGG16MinusMinus(num_classes, target_image_size)
    v16mm.to(device)
    if load_parameters:
        logging.warning(
            'Loading existing model parameters to continue training')
        v16mm.load_state_dict(torch.load(
            config['model']['parameters'].replace(r'{id}', model_id)
        ))

    logging.info('Name       |      Params | Structure')
    total_parameters = 0
    for name, module in v16mm.named_modules():
        if isinstance(module, nn.Sequential):
            # Sequential() is like a wrapper module, we will print layers twice
            # if we don't skip it.
            continue
        if len(name) == 0:
            # Will print the entire model as a layer, let's skip it
            continue
        layer_parameters = sum(p.numel() for p in module.parameters() if p.requires_grad)
        total_parameters += layer_parameters
        logging.info(f'{name.ljust(10)} | {layer_parameters: >11,} | {module}')
    logging.info(f'{"Total".ljust(10)} | {total_parameters: >11,} | NA')

    training_samples_dir = config['dataset']['training']
    logging.info(f'Loading samples from [{training_samples_dir}]')
    # Define the dataset and data loader for the training set
    train_loader, train_loader_for_eval, val_loader = get_data_loaders(
        training_samples_dir, config['model']['random_seeds'][model_id]
    )
    save_transformed_samples(
        train_loader,
        os.path.join(config['model']['diagnostics_dir'], 'preview', f'training_samples_{model_id}'),
        30
    )
    save_transformed_samples(
        train_loader_for_eval,
        os.path.join(config['model']['diagnostics_dir'], 'preview', f'training_samples_for_eval_{model_id}'),
        30)
    save_transformed_samples(
        val_loader,
        os.path.join(config['model']['diagnostics_dir'], 'preview', f'test_samples_{model_id}'),
        5
    )

    # Define the loss function, optimizer and learning rate scheduler
    loss_fn = nn.CrossEntropyLoss()

    # weight_decay is L2 regularization's lambda
    optimizer = optim.Adam(
        v16mm.parameters(),
        lr=(0.001 if lr is None else lr),
        weight_decay=3e-4
    )
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.8)
    start_ts = time.time()
    # Train the model
    for epoch in range(epochs):
        logging.info('\n========================================\n'
                     f'Epoch {epoch + 1} / {epochs} started, '
                     f'lr: {scheduler.get_last_lr()}'
                     '\n========================================')

        v16mm.train()   # switch to training mode
        for batch_idx, (images, y_trues) in enumerate(train_loader):
            # Every data instance is an input + label pair
            images, y_trues = images.to(device), y_trues.to(device)

            # Zero your gradients for every batch!
            optimizer.zero_grad()
            # Make predictions for this batch
            y_preds = v16mm(images)

            # Compute the loss
            loss = loss_fn(y_preds, y_trues)

            # l1_lambda = 1e-4
            # l1_norm = sum(torch.linalg.norm(p, 1) for p in v16mm.parameters())
            # weight_decay is L2 reg already
            # l2_lambda = 1e-3
            # l2_norm = sum(p.pow(2.0).sum() for p in v16mm.parameters())

            # loss = loss + l1_lambda * l1_norm  # + l2_lambda * l2_norm
            # Computes the gradient of current tensor w.r.t. graph leaves.
            loss.backward()

            # Adjust learning weights
            optimizer.step()

            if (((batch_idx + 1) % 500 == 0) or
                    (batch_idx + 1 == len(train_loader))):
                logging.info(f"Step {batch_idx+1}/{len(train_loader)}, "
                             f"loss: {loss.item():.5f}")

        scheduler.step()
        logging.info('Evaluating model after this epoch')
        evalute_model_classification(v16mm, num_classes, train_loader,
                                     f'training_eval-off_{model_id}', 50)

        # switch to evaluation mode
        v16mm.eval()
        evalute_model_classification(v16mm, num_classes, train_loader_for_eval,
                                     f'training_eval-on_{model_id}', 50)

        evalute_model_classification(v16mm, num_classes, val_loader,
                                     f'test_{model_id}', 10)

        save_params(v16mm, model_id)
        save_ts_model(v16mm, model_id)
        eta = start_ts + (time.time() - start_ts) / ((epoch + 1) / epochs)
        logging.info(
            f'ETA: {dt.datetime.fromtimestamp(eta).astimezone().isoformat()}'
            f', estimated training duration: {(eta - start_ts)/3600:.1f} hrs'
        )
    return v16mm


def generate_curves(filename: str, mv_window: int = 1) -> None:
    csv_path = os.path.join(
        config['model']['diagnostics_dir'], 'training', f'{filename}.csv'
    )
    img_path = os.path.join(
        config['model']['diagnostics_dir'], 'training',
        f'{filename}_mv{mv_window}.png'
    )
    if os.path.isfile(csv_path) is not True:
        raise FileNotFoundError(f'{csv_path} not found')
    df = pd.read_csv(csv_path)

    plt.clf()
    for col in df.columns:
        df[col] = df[col].rolling(window=mv_window).mean()
        plt.plot(df.index, df[col], label=col)

    # Customize chart
    plt.title(f'{filename}_{mv_window}')
    plt.xlabel('Epochs')
    plt.ylabel('Metrics')
    plt.grid(True)
    plt.legend()
    plt.savefig(img_path)


def main() -> None:

    global config, device
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s.%(msecs)03d | %(levelname)7s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    ap = argparse.ArgumentParser()
    ap.add_argument('--load-parameters', '-l', action='store_true',
                    help='load existing parameters for continue training')
    ap.add_argument('--config-path', '-c', dest='config-path', required=True,
                    help='Config file path')
    ap.add_argument('--learning-rate', '-lr', dest='learning_rate', type=float,
                    help='Specify a learning rate', default=0.001)
    ap.add_argument('--epochs', '-e', dest='epochs', type=int, default=10)
    ap.add_argument('--model-id', '-i', dest='model_id', required=True)
    ap.add_argument('--cuda-device-id', '-d', dest='cuda-device-id',
                    default='cuda',
                    help=('Specify GPU to use following CUDA semantics. '
                          'Sample values include "cuda"/"cuda:0"/"cuda:1"'))
    args = vars(ap.parse_args())

    with open(args['config-path']) as j:
        config = json.load(j)
    device = helper.get_cuda_device(args['cuda-device-id'])
    properties = torch.cuda.get_device_properties(device)
    logging.info(f"GPU Model: {properties.name}")
    logging.info(f"GPU Memory: {properties.total_memory / 1024**3:.2f} GB")
    logging.info(f"GPU CUDA semantics: {device}")

    target_img_size = (
        config['model']['input_image_size']['height'],
        config['model']['input_image_size']['width']
    )
    set_seed(config['model']['random_seeds'][args['model_id']])
    helper.init_transforms(target_img_size)
    train(
        args['load_parameters'], args['model_id'],
        config['model']['num_output_class'], target_img_size,
        args['learning_rate'], args['epochs']
    )
    logging.info('Training completed')


if __name__ == '__main__':
    main()
