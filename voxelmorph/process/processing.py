import os
import SimpleITK as sitk
import numpy as np
from matplotlib import pyplot as plt
import torch

from utils.utilize import plotorsave_ct_scan, get_project_path, make_dir

# import ants

# DIRLAB 4DCT 1-10例的 z y x
case_cfg = {
    1: (94, 256, 256),
    2: (112, 256, 256),
    3: (104, 256, 256),
    4: (99, 256, 256),
    5: (106, 256, 256),
    6: (128, 512, 512),
    7: (136, 512, 512),
    8: (128, 512, 512),
    9: (128, 512, 512),
    10: (120, 512, 512),
}


def imgTomhd(file_folder, m_path, f_path, datatype, shape, case, resample=False):
    for file_name in os.listdir(file_folder):
        is_fixed = False
        # T50为参考图像
        if 'T50' in file_name:
            is_fixed = True
        file_path = os.path.join(file_folder, file_name)
        file = np.memmap(file_path, dtype=datatype, mode='r')
        if shape:
            file = file.reshape(shape)

        img = sitk.GetImageFromArray(file)
        if resample:
            # 统一采样到1*1*2.5mm
            img = img_resmaple([1, 1, 2.5], ori_img_file=img)

        target_filepath = os.path.join(m_path,
                                       f"dirlab_case{case}_T" + file_name[file_name.find('T') + 1] + "0_moving.mhd")
        if is_fixed:
            for i in range(10):
                if i == 5:
                    continue
                new_name = f'dirlab_case{case}_T' + str(i) + '0_fixed.mhd'
                target_filepath = os.path.join(f_path, new_name)
                if not os.path.exists(target_filepath):
                    sitk.WriteImage(img, target_filepath)

        if not os.path.exists(target_filepath):
            sitk.WriteImage(img, target_filepath)

    print("{} convert done".format(file_folder))


def data_standardization_0_n(range, img):
    if torch.is_tensor(img):
        return range * (img - torch.min(img)) / (torch.max(img) - torch.min(img))
    else:
        return range * (img - np.min(img)) / (np.max(img) - np.min(img))


def data_standardization_mean_std(img):
    return (img - np.mean(img)) / np.std(img)


# def affiine(move_img, fix_img, save_path):
#     outs = ants.registration(fix_img, move_img, type_of_transforme='Affine')
#     reg_img = outs['warpedmovout']
#     ants.image_write(reg_img, save_path)


def read_mhd(mhd_dir):
    for file_name in os.listdir(mhd_dir):
        mhd_file = os.path.join(mhd_dir, file_name)
        itkimage = sitk.ReadImage(mhd_file)
        ct_value = sitk.GetArrayFromImage(itkimage)  # 这里一定要注意，得到的是[z,y,x]格式
        direction = itkimage.GetDirection()  # mhd文件中的TransformMatrix
        origin = np.array(itkimage.GetOrigin())
        spacing = np.array(itkimage.GetSpacing())  # 文件中的ElementSpacing
        plotorsave_ct_scan(ct_value, "plot")


def img_resmaple(new_spacing, resamplemethod=sitk.sitkLinear, ori_img_file=None, ori_img_path=None):
    """
        @param ori_img_file: sitk.Image
        @param ori_img_path: 原始的itk图像路径，一般为.mhd 两个参数二选一
        @param target_img_file: 保存路径
        @param new_spacing: 目标重采样的spacing，如[0.585938, 0.585938, 0.4]
        @param resamplemethod: itk插值⽅法: sitk.sitkLinear-线性、sitk.sitkNearestNeighbor-最近邻、sitk.sitkBSpline等，SimpleITK源码中会有各种插值的方法，直接复制调用即可
    """
    data = sitk.ReadImage(ori_img_path) if ori_img_file == None else ori_img_file  # 根据路径读取mhd文件
    original_spacing = data.GetSpacing()  # 获取图像重采样前的spacing
    original_size = data.GetSize()  # 获取图像重采样前的分辨率

    # 有原始图像size和spacing得到真实图像大小，用其除以新的spacing,得到变化后新的size
    new_shape = [
        int(np.round(original_spacing[0] * original_size[0] / new_spacing[0])),
        int(np.round(original_spacing[1] * original_size[1] / new_spacing[1])),
        int(np.round(original_spacing[2] * original_size[2] / new_spacing[2])),
    ]
    print("处理后新的分辨率:{}".format(new_shape))

    # 重采样构造器
    resample = sitk.ResampleImageFilter()

    resample.SetOutputSpacing(new_spacing)  # 设置新的spacing
    resample.SetOutputOrigin(data.GetOrigin())  # 原点坐标没有变，所以还用之前的就可以了
    resample.SetOutputDirection(data.GetDirection())  # 方向也未变
    resample.SetSize(new_shape)  # 分辨率发生改变
    resample.SetInterpolator(resamplemethod)  # 插值算法
    data = resample.Execute(data)  # 执行操作

    return data
    # sitk.WriteImage(data, os.path.join(ori_img_file, '_new'))  # 将处理后的数据，保存到一个新的mhd文件中


def resize_image_itk(itkimage, newSize, resamplemethod=sitk.sitkLinear):
    resampler = sitk.ResampleImageFilter()
    originSize = itkimage.GetSize()  # 原来的体素块尺寸
    originSpacing = itkimage.GetSpacing()
    newSize = np.array(newSize, float)
    newSpacing = originSpacing * originSize / newSize
    newSize = newSize.astype(np.int)  # spacing肯定不能是整数
    resampler.SetReferenceImage(itkimage)  # 需要重新采样的目标图像
    resampler.SetSize(newSize.tolist())
    resampler.SetOutputSpacing(newSpacing.tolist())
    resampler.SetTransform(sitk.Transform(3, sitk.sitkIdentity))
    resampler.SetInterpolator(resamplemethod)
    itkimgResampled = resampler.Execute(itkimage)  # 得到重新采样后的图像
    return itkimgResampled


if __name__ == '__main__':

    project_folder = get_project_path("4DCT").split("4DCT")[0]

    # read_mhd(os.path.join(project_folder, f'datasets/dirlab/Case1Pack/Images_mhd'))

    # dirlab数据集img转mhd
    # for item in case_cfg.items():
    #     case = item[0]
    #     shape = item[1]
    #     img_path = os.path.join(project_folder, f'datasets/dirlab/img/Case{case}Pack/Images')
    #     moving_path = os.path.join(project_folder, f'datasets/registration/moving')
    #     fixed_path = os.path.join(project_folder, f'datasets/registration/fixed')
    #     make_dir(moving_path)
    #     make_dir(fixed_path)
    #
    #     imgTomhd(img_path, moving_path, fixed_path, np.int16, shape, case, True)

    # 真实病例
    img_path = os.path.join(project_folder, f'datasets/4DCT_nii/')
    for file_name in os.listdir(img_path):
        mhd_file = os.path.join(img_path, file_name)
        itkimage = sitk.ReadImage(mhd_file)
        ct_value = sitk.GetArrayFromImage(itkimage)  # 这里一定要注意，得到的是[z,y,x]格式
        direction = itkimage.GetDirection()  # mhd文件中的TransformMatrix
        origin = np.array(itkimage.GetOrigin())
        spacing = np.array(itkimage.GetSpacing())  # 文件中的ElementSpacing
        plotorsave_ct_scan(ct_value, "plot")
