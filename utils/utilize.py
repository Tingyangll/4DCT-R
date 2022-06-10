import os
import torch
import SimpleITK as sitk
import numpy as np
from matplotlib import pyplot as plt
from PIL import Image
import cv2
import process.processing
import torchvision.transforms as transform


def save_png(imgs_numpy, save_path, save_name):
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    img_numpy = process.processing.data_standardization_0_255(imgs_numpy)
    cv2.imwrite(os.path.join(save_path, save_name + ".png"), img_numpy)


def make_dir(log_dir):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    return log_dir


def get_project_path(project_name):
    project_path = os.path.abspath(os.path.dirname(__file__))
    root_path = project_path[:project_path.find("{}".format(project_name)) + len("{}".format(project_name))]
    return root_path


def loadfileToarray(file_folder, datatype, shape=None):
    file_name_list = os.listdir(file_folder)
    file_list = []
    for i, file_name in enumerate(file_name_list):
        file_path = os.path.join(file_folder, file_name)
        if os.path.isdir(file_path):
            # 为dcm文件
            # file = data_processing.readDicomSeries(file_path)
            pass
        else:
            file = np.memmap(file_path, dtype=datatype, mode='r')
            if datatype == np.float16:
                file = file.astype('float32')
        if shape:
            file = file.reshape(shape)

        file_list.append(file)
    files_array = np.array(file_list)

    return files_array


def dvf_save_nii(project_name, dvf_file):
    project_path = get_project_path(project_name)
    dvf_path = os.path.join(project_path, dvf_file)
    dvf = loadfileToarray(dvf_path, np.float32).reshape(3, 150, 256, 256).transpose(2, 3, 1, 0)
    sitk_dvf = sitk.GetImageFromArray(dvf)
    sitk.WriteImage(sitk_dvf, "dvf.nii")


def showimg(image: list, cmap='gray'):
    """
    draw single pic every group
    :param image:
    :param cmap:
    :return:
    """
    length = len(image)
    for i in range(length):
        plt.imshow(image[i][:, 90, :], cmap=cmap)  # D*H*W
        plt.show()


def plot_ct_scan(scan, num_column=4, jump=1):
    '''
    画出3D-CT 所有的横断面切片
    :param scan: A NumPy ndarray from a SimpleITK Image
    :param num_column:
    :param jump: 间隔多少画图
    :return:
    '''
    num_slices = len(scan)
    num_row = (num_slices // jump + num_column - 1) // num_column
    f, plots = plt.subplots(num_row, num_column, figsize=(num_column * 5, num_row * 5))
    for i in range(0, num_row * num_column):
        plot = plots[i % num_column] if num_row == 1 else plots[i // num_column, i % num_column]
        plot.axis('off')
        if i < num_slices // jump:
            plot.imshow(scan[i * jump], cmap="gray")


def transform_convert(img, transform):
    """
    param img_tensor: tensor
    param transforms: torchvision.transforms
    """
    img_tensor = img.clone()
    if 'Normalize' in str(transform):
        normal_transform = list(filter(lambda x: isinstance(x, transform.Normalize), transform.transforms))
        mean = torch.tensor(normal_transform[0].mean, dtype=img_tensor.dtype, device=img_tensor.device)
        std = torch.tensor(normal_transform[0].std, dtype=img_tensor.dtype, device=img_tensor.device)
        img_tensor.mul_(std[:, None, None]).add_(mean[:, None, None])

    img_tensor = img_tensor.transpose(0, 2).transpose(0, 1)  # C x H x W  ---> H x W x C

    if 'ToTensor' in str(transform) or img_tensor.max() < 1:
        img_tensor = img_tensor.detach().numpy() * 255

    if isinstance(img_tensor, torch.Tensor):
        img_tensor = img_tensor.numpy()

    if img_tensor.shape[2] == 3:
        img = Image.fromarray(img_tensor.astype('uint8')).convert('RGB')
    elif img_tensor.shape[2] == 1:
        img = Image.fromarray(img_tensor.astype('uint8')).squeeze()
    else:
        raise Exception("Invalid img shape, expected 1 or 3 in axis 2, but got {}!".format(img_tensor.shape[2]))

    return img


if __name__ == '__main__':
    # simpleITK x, y, z
    # numpy z, y, x

    case = 3
    shape = (104, 256, 256)
    img_path = f'/home/cqut-415/project/xxf/datasets/dirlab/Case{case}Pack/Images'
    img_array = loadfileToarray(img_path, np.float16, shape)
    # showimg(img_array, cmap='gray')
    img = sitk.GetImageFromArray(img_array[0])
    scan = sitk.GetArrayFromImage(img)
    print("1")
