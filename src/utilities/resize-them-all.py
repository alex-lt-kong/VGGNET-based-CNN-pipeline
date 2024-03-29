from PIL import Image
from typing import Tuple

from .. import helper
import argparse
import os


def resize_images(src_dir: str, dst_dir: str, dst_size: Tuple[int, int]) -> None:

    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    for filename in os.listdir(src_dir):
        if filename.endswith('.jpg') or filename.endswith('.png'):
            image_path = os.path.join(src_dir, filename)
            image = Image.open(image_path)

            if image.size[0] == dst_size[0] and image.size[1] == dst_size[1]:
                print(f'{filename}\'s size is already the same as dst_size, skipping')
                continue
            resized_image = image.resize(dst_size)
            output_path = os.path.join(dst_dir, filename)
            resized_image.save(output_path)

            print(f'Resized [{filename}] and saved to [{output_path}]')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-dir', '-s', dest='source-dir', required=True)
    ap.add_argument('--dest-dir', '-d', dest='dest-dir', required=True)
    args = vars(ap.parse_args())
    # size = (426, 224)  # size in in (w, h)
    raise NotImplementedError('helper.target_img_size is obsolete')
    resize_images(args['source-dir'], args['dest-dir'], helper.target_img_size)


if __name__ == '__main__':
    main()
