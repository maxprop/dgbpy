#
# (C) dGB Beheer B.V.; (LICENSE) http://opendtect.org/OpendTect_license.txt
# AUTHOR   : Olawale Ibrahim
# DATE     : October 2021
#
# dGB PyTorch machine learning models in TorchUserModel format
#

from dgbpy.torch_classes import TorchUserModel, DataPredType, OutputType, DimType

class dGB_UnetSeg(TorchUserModel):
  uiname = 'dGB UNet Segmentation'
  uidescription = 'dGBs Unet image segmentation'
  predtype = DataPredType.Classification
  outtype = OutputType.Image
  dimtype = DimType.Any
  
  def _make_model(self, model_shape, nroutputs, nrattribs):
    from dgbpy.dgbtorch import getModelDims
    ndim = getModelDims(model_shape, 'channels_first')
    model = UNet(in_channels=nrattribs, n_blocks=1, out_channels=nroutputs, dim=ndim)
    return model

from dgbpy.torch_classes import Net, create_resnet_block, UNet
import torch.nn as nn

class dGB_Simple_Net_Classifier(TorchUserModel):
    uiname = 'Simple Net Classifier'
    uidescription = 'dGbs Simple Net Classifier Model in TorchUserModel form'
    predtype = DataPredType.Classification
    outtype = OutputType.Pixel
    dimtype = DimType.Any

    def _make_model(self, model_shape, nroutputs, nrattribs):
      from dgbpy.dgbtorch import getModelDims
      ndim = getModelDims(model_shape, 'channels_first')
      model = Net(output_classes=nroutputs, dim=ndim, nrattribs=nrattribs)
      return model

class dGB_UnetReg(TorchUserModel):
  uiname = 'dGB UNet Regression'
  uidescription = 'dGBs Unet image regression'
  predtype = DataPredType.Continuous
  outtype = OutputType.Image
  dimtype = DimType.Any
  
  def _make_model(self, model_shape, nroutputs, nrattribs):
    from dgbpy.dgbtorch import getModelDims
    ndim = getModelDims(model_shape, 'channels_first')
    model = UNet(in_channels=nrattribs, n_blocks=1, out_channels=nroutputs, dim=ndim)
    return model

class dGB_ResNet18(TorchUserModel):
    uiname = 'ResNet 18 Classifier'
    uidescription = 'dGBs ResNet Classifier Model in TorchUserModel form'
    predtype = DataPredType.Classification
    outtype = OutputType.Pixel
    dimtype = DimType.Any

    def _make_model(self, model_shape, nroutputs, nrattribs):
      from dgbpy.dgbtorch import getModelDims
      ndim = getModelDims(model_shape, 'channels_first')
      model = ResNet18(nroutputs, dim=ndim, nrattribs=nrattribs)
      return model

def ResNet18(nroutputs, dim, nrattribs):
    from torch.nn import Conv1d, Conv2d, Conv3d, BatchNorm1d, BatchNorm2d, BatchNorm3d

    if dim==3:
      Conv = Conv3d
      BatchNorm = BatchNorm3d
    elif dim==2:
      Conv = Conv2d
      BatchNorm = BatchNorm2d
    elif dim==1 or dim==0:
      Conv = Conv1d
      BatchNorm = BatchNorm1d

    b0 = nn.Sequential(
    Conv(in_channels = nrattribs, out_channels = 4, kernel_size = 3, stride = 1, padding = 1),
    BatchNorm(num_features = 4),
    nn.ReLU())

    b1 = nn.Sequential(*create_resnet_block(input_filters = 4, output_filters = 4, num_residuals = 1, first_block = True, ndims=dim))
    if dim==3:
      model = nn.Sequential(
      b0, b1,
      nn.AdaptiveAvgPool2d(output_size = (1, 1)),
      nn.Flatten(),
      nn.Linear(in_features = 36, out_features = nroutputs))
    elif dim==2:
      model = nn.Sequential(
      b0, b1,
      nn.AdaptiveAvgPool2d(output_size = (1, 1)),
      nn.Flatten(),
      nn.Linear(in_features = 4, out_features = nroutputs))
    elif dim==1 or dim==0:
      model = nn.Sequential(
      b0, b1,
      nn.AdaptiveAvgPool2d(output_size = (1, 1)),
      nn.Flatten(),
      nn.Linear(in_features = 1, out_features = nroutputs))
    return model
    
class dGB_Simple_Net_Regressor(TorchUserModel):
    uiname = 'Simple Net Regressor'
    uidescription = 'dGbs Simple Net Regressor Model in TorchUserModel form'
    predtype = DataPredType.Continuous
    outtype = OutputType.Pixel
    dimtype = DimType.Any

    def _make_model(self, model_shape, nroutputs, nrattribs):
      from dgbpy.dgbtorch import getModelDims
      ndim = getModelDims(model_shape, 'channels_first')
      model = Net(model_shape=model_shape, output_classes=nroutputs, dim=ndim, nrattribs=nrattribs)
      return model