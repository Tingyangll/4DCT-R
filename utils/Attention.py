import torch
import torch.nn as nn
import torch.nn.functional as F


class Mish(nn.Module):
    def __init__(self):
        super(Mish, self).__init__()

    def forward(self, x):
        return x * torch.tanh(F.softplus(x))


# basic conv block
class BasicConv3D(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=1, stride=1, padding=0, active=True):
        super(BasicConv3D, self).__init__()
        self.active = active
        # self.bn = nn.BatchNorm1d(in_channels)
        if self.active == True:
            self.activation = Mish()
        self.conv = nn.Conv3d(in_channels, out_channels, kernel_size=kernel_size, stride=stride, padding=padding,
                              bias=False)
        # self.dropout = nn.Dropout(0.5)

    def forward(self, x):
        # x = self.bn(x)
        if self.active == True:
            x = self.activation(x)
        x = self.conv(x)

        return x


class Resblock3D(nn.Module):
    def __init__(self, channels, out_channels, residual_activation=nn.Identity()):
        super(Resblock3D, self).__init__()

        self.channels = channels
        self.out_channels = out_channels
        if self.channels != self.out_channels:
            self.res_conv = BasicConv3D(channels, out_channels, 1)

        self.activation = Mish()
        self.block = nn.Sequential(
            BasicConv3D(channels, out_channels // 2, 1),
            BasicConv3D(out_channels // 2, out_channels, 1, active=False)
        )

    def forward(self, x):
        residual = x
        if self.channels != self.out_channels:
            residual = self.res_conv(x)
        return self.activation(residual + self.block(x))


class Self_Attn(nn.Module):
    """ Self attention Layer"""

    def __init__(self, in_dim, out_dim):
        super(Self_Attn, self).__init__()

        self.in_dim = in_dim
        self.out_dim = out_dim

        # 查询卷积
        self.query_conv = BasicConv3D(in_dim, out_dim)

        self.value_conv = nn.Sequential(
            Resblock3D(in_dim, out_dim),
            Resblock3D(out_dim, out_dim)
        )

        # if in_dim != out_dim:
        #    self.short_conv = BasicConv1D(in_dim, out_dim)

        # self.alpha = nn.Parameter(torch.ones(1))
        self.beta = nn.Parameter(torch.zeros(1))

        self.softmax = nn.Softmax(dim=-1)  #

    def forward(self, x):
        """
            inputs :
                x : input feature maps( B X C X N)  32, 1024, 64
            returns :
                out : self attention value + input feature
                attention: B X N X N (N is Width*Height)
        """

        proj_query = self.query_conv(x).permute(0, 2, 3, 4, 1)  # B,C,D,H,W-> B,D,H,W,C
        proj_key = proj_query.permute(0, 1, 2, 4, 3)  # B,D,H,W,C-> B,D,H,C,W

        energy = torch.matmul(proj_query, proj_key)  # transpose check    B D H W W

        attention = self.softmax(energy)  # B D H W W

        proj_value = self.value_conv(x)  # proj_key# #B, C, D, H, W

        out_x = torch.matmul(proj_value.permute(0, 2, 3, 1, 4), attention).permute(0, 3, 1, 2,
                                                                                   4)  # B,D,H,C,W -> B,C,D,H,W

        out = self.beta * out_x + proj_value

        return out


class Cross_attention(nn.Module):
    """ Self attention Layer"""

    def __init__(self, in_dim, out_dim):
        super(Cross_attention, self).__init__()

        self.in_dim = in_dim
        self.out_dim = out_dim

        self.query_conv = BasicConv3D(in_dim, out_dim)

        self.beta = nn.Parameter(torch.zeros(1))
        self.activate = nn.LeakyReLU(0.2)

    def forward(self, x, y):  # B, C, D, H, W
        """
            inputs :
                x : current level feature maps ( B, C, D, H, W )
                y : i-1 level feature maps
            returns :
                out : B, C, D, H, W
        """
        # proj_query_x = self.query_conv(x).permute(0, 2, 3, 1, 4)  # B D H C W
        #
        # proj_key_y = self.query_conv(y).permute(0, 2, 3, 4, 1)  # B D H W C
        #
        # energy_xy = torch.matmul(proj_query_x, proj_key_y)  # xi 对 y所有点的注意力得分   B D H C C
        #
        # attention_xy = self.activate(energy_xy)  # B D H C C
        # attention_yx = self.activate(energy_xy.permute(0, 1, 2, 4, 3))  # BDHCC
        #
        # proj_value_x = proj_query_x  # self.value_conv_x(x) # [B, out_dim, 64]  B D H C W
        # proj_value_y = proj_key_y.permute(0, 1, 2, 4,
        #                                   3)  # self.value_conv_x(y) # [B, out_dim, 64]  B D H W C -> B D H C W
        #
        # out_x = torch.matmul(attention_xy, proj_value_x)  # [B, out_dim, D, H, W]  B D H C W
        # out_x = self.beta * out_x + proj_value_x  # self.kama*
        #
        # out_y = torch.matmul(attention_yx, proj_value_y)  # [B, out_dim, D, H, W] B D H C W
        # out_y = self.beta * out_y + proj_value_y  # self.kama *
        #
        # # # At last, a mutiplication between out_x and out_y then follow an active function, instead of concat
        # # return self.activate(torch.mul(out_x, out_y)).permute(0, 3, 1, 2, 4)  # B D H C W -> B,C,D,H,W
        # return torch.cat([out_x, out_y], dim=3).permute(0, 3, 1, 2, 4)  # B D H C W -> B,C,D,H,W

        # BCDHW B DHW C
        # B C DHW -> B C 1
        # B DHW 1

        proj_query_x = self.query_conv(x).permute(0, 3, 4, 1, 2)  # B H W C D

        proj_key_y = self.query_conv(y).permute(0, 3, 4, 2, 1)  # B H W D C

        energy_xy = torch.matmul(proj_query_x, proj_key_y)  # xi 对 y所有点的注意力得分   B H W C C

        attention_xy = self.activate(energy_xy)  # B H W C C
        attention_yx = self.activate(energy_xy.permute(0, 1, 2, 4, 3))  # BHWCC

        proj_value_x = proj_query_x  # B H W C D
        proj_value_y = proj_key_y.permute(0, 1, 2, 4,
                                          3)  # B H W C D

        out_x = torch.matmul(attention_xy, proj_value_x)  # B H W C D
        out_x = self.beta * out_x + proj_value_x  # self.kama*

        out_y = torch.matmul(attention_yx, proj_value_y)  # B H W C D
        out_y = self.beta * out_y + proj_value_y  # self.kama *

        # # At last, a mutiplication between out_x and out_y then follow an active function, instead of concat
        # return self.activate(torch.mul(out_x, out_y)).permute(0, 3, 1, 2, 4)  # B D H C W -> B,C,D,H,W
        return torch.cat([out_x, out_y], dim=3).permute(0, 3, 4, 1, 2)  # B,C,D,H,W


class Cross_attention_2(nn.Module):
    """ Self attention Layer"""

    def __init__(self, in_dim, out_dim):
        super(Cross_attention_2, self).__init__()
        self.in_dim = in_dim
        self.out_dim = out_dim

        self.query_conv = BasicConv3D(in_dim, out_dim, kernel_size=3,padding=1)

        self.beta = nn.Parameter(torch.zeros(1))
        self.activate = nn.LeakyReLU(0.2)

    def forward(self, x, y):  # B, C, D, H, W
        """
            inputs :
                x : current level feature maps ( B, C, D, H, W )
                y : i-1 level feature maps
            returns :
                out : B, C, D, H, W
        """
        proj_query_x = self.query_conv(x).permute(0, 2, 3, 1, 4)  # B D H C W

        proj_key_y = self.query_conv(y).permute(0, 2, 3, 4, 1)  # B D H W C

        energy_xy = torch.matmul(proj_query_x, proj_key_y)  # xi 对 y所有点的注意力得分   B D H C C

        attention_xy = self.activate(energy_xy)  # B D H C C
        attention_yx = self.activate(energy_xy.permute(0, 1, 2, 4, 3))  # BDHCC

        proj_value_x = proj_query_x  # self.value_conv_x(x) # [B, out_dim, 64]  B D H C W
        proj_value_y = proj_key_y.permute(0, 1, 2, 4,
                                          3)  # self.value_conv_x(y) # [B, out_dim, 64]  B D H W C -> B D H C W

        out_x = torch.matmul(attention_xy, proj_value_x)  # [B, out_dim, D, H, W]  B D H C W
        out_x = self.beta * out_x + proj_value_x  # self.kama*

        out_y = torch.matmul(attention_yx, proj_value_y)  # [B, out_dim, D, H, W] B D H C W
        out_y = self.beta * out_y + proj_value_y  # self.kama *

        # # At last, a mutiplication between out_x and out_y then follow an active function, instead of concat
        # return self.activate(torch.mul(out_x, out_y)).permute(0, 3, 1, 2, 4)  # B D H C W -> B,C,D,H,W
        return torch.cat([out_x.permute(0, 3, 1, 2, 4)+x, out_y.permute(0, 3, 1, 2, 4)+y], dim=1)  # B D H C W -> B,C,D,H,W

        # BCDHW B DHW C
        # B C DHW -> B C 1
        # B DHW 1

        # proj_query_x = self.query_conv(x).permute(0, 3, 4, 1, 2)  # B H W C D
        #
        # proj_key_y = self.query_conv(y).permute(0, 3, 4, 2, 1)  # B H W D C
        #
        # energy_xy = torch.matmul(proj_query_x, proj_key_y)  # xi 对 y所有点的注意力得分   B H W C C
        #
        # attention_xy = self.activate(energy_xy)  # B H W C C
        # attention_yx = self.activate(energy_xy.permute(0, 1, 2, 4, 3))  # BHWCC
        #
        # proj_value_x = proj_query_x  # B H W C D
        # proj_value_y = proj_key_y.permute(0, 1, 2, 4,
        #                                   3)  # B H W C D
        #
        # out_x = torch.matmul(attention_xy, proj_value_x)  # B H W C D
        # out_x = self.beta * out_x + proj_value_x  # self.kama*
        #
        # out_y = torch.matmul(attention_yx, proj_value_y)  # B H W C D
        # out_y = self.beta * out_y + proj_value_y  # self.kama *
        #
        # # # At last, a mutiplication between out_x and out_y then follow an active function, instead of concat
        # # return self.activate(torch.mul(out_x, out_y)).permute(0, 3, 1, 2, 4)  # B D H C W -> B,C,D,H,W
        # return torch.cat([out_x, out_y], dim=3).permute(0, 3, 4, 1, 2)  # B,C,D,H,W


# cross
class Cross_attention_multi(nn.Module):
    """ Self attention Layer"""

    def __init__(self, in_dim, out_dim):
        super().__init__()

        self.in_dim = in_dim
        self.out_dim = out_dim
        self.activate = nn.LeakyReLU(0.2)

        # self.patch_size=10
        self.patch_size = 9

        self.conv_img = nn.Sequential(
            nn.Conv3d(self.in_dim, self.out_dim, kernel_size=(3, 3, 3), stride=1, padding=1)
        )

        self.conv_feamap = nn.Sequential(
            nn.Conv3d(self.in_dim, self.out_dim, kernel_size=(3, 3, 3), stride=1, padding=1)
        )

        self.unfold = nn.Unfold(kernel_size=(self.patch_size, self.patch_size),
                                stride=(self.patch_size, self.patch_size))

        self.resolution_trans = nn.Sequential(
            nn.Linear(self.patch_size * self.patch_size, 2 * self.patch_size * self.patch_size, bias=False),
            nn.Linear(2 * self.patch_size * self.patch_size, self.patch_size * self.patch_size, bias=False),
            nn.LeakyReLU(0.2)
        )

    def forward(self, x, y):  # B, C, D, H, W
        """
            inputs :
                x : current level feature maps ( B, C, D, H, W )
                y : i-1 level feature maps
            returns :
                out : B, C, D, H, W
        """
        attentions = []

        # step 1. adjust the channel of x, y
        x = self.conv_img(x)
        y = self.conv_feamap(y)

        C = x.shape[1]
        D = x.shape[2]
        H = x.shape[3]
        W = x.shape[4]

        # step 2. let x, y reshape (B, C, D, HW)
        x_reshape = x.reshape(1, C, D, H * W)
        y_reshape = y.reshape(1, C, D, H * W)

        for i in range(C):
            unfold_img = self.unfold(x_reshape[:, i: i + 1, :, :]).transpose(-1, -2)  # B, DHW/d/d, d*d
            unfold_img = self.resolution_trans(unfold_img)

            unfold_feamap = self.unfold(y_reshape[:, i: i + 1, :, :])  # B, d*d, DHW/d/d
            unfold_feamap = self.resolution_trans(unfold_feamap.transpose(-1, -2)).transpose(-1, -2)

            att = torch.matmul(unfold_img, unfold_feamap) / (self.patch_size * self.patch_size)  # B, DHW/d/d, DHW/d/d
            # att = torch.matmul(unfold_img, unfold_feamap)  # B, DHW/d/d, DHW/d/d

            att = torch.unsqueeze(att, 1)

            attentions.append(att)

        attentions = torch.cat((attentions), dim=1)

        return attentions


class Cross_attention_3(nn.Module):
    """ Self attention Layer"""

    def __init__(self, in_dim, out_dim):
        super(Cross_attention_3, self).__init__()

        self.in_dim = in_dim
        self.out_dim = out_dim
        self.activate = nn.LeakyReLU(0.2)

        # self.patch_size=10
        self.patch_size = 9

        self.pool = nn.AdaptiveAvgPool1d(self.patch_size * self.patch_size)

        self.conv_img = nn.Sequential(
            nn.Conv3d(self.in_dim, self.out_dim, kernel_size=(1, 1, 1), stride=1)
        )

        self.conv_feamap = nn.Sequential(
            nn.Conv3d(self.in_dim, self.out_dim, kernel_size=(1, 1, 1), stride=1)
        )

        self.unfold = nn.Unfold(kernel_size=(self.patch_size, self.patch_size),
                                stride=(self.patch_size, self.patch_size))

        self.resolution_trans = nn.Sequential(
            nn.Linear(self.patch_size * self.patch_size, 2 * self.patch_size * self.patch_size, bias=False),
            nn.Linear(2 * self.patch_size * self.patch_size, self.patch_size * self.patch_size, bias=False),
            nn.LeakyReLU(0.2)
        )

    def forward(self, x, y):  # B, C, D, H, W
        """
            inputs :
                x : current level feature maps ( B, C, D, H, W )
                y : i-1 level feature maps
            returns :
                out : B, C, D, H, W
        """
        attentions = []
        # step 1. adjust the channel of x, y
        x = self.conv_img(x)
        y = self.conv_feamap(y)

        C = x.shape[1]
        D = x.shape[2]
        H = x.shape[3]
        W = x.shape[4]

        # step 2. let x, y reshape (B, C, D, HW)
        x_reshape = x.reshape(1, C, D, H * W)
        y_reshape = y.reshape(1, C, D, H * W)

        fold_layer = torch.nn.Fold(output_size=(x.size()[-3], x.size()[-1] * x.size()[-2]),
                                   kernel_size=(self.patch_size, self.patch_size),
                                   stride=(self.patch_size, self.patch_size))

        for i in range(C):
            unfold_img = self.unfold(x_reshape[:, i: i + 1, :, :]).transpose(-1, -2)  # B, DHW/d/d, d*d
            unfold_img = self.resolution_trans(unfold_img)

            unfold_feamap = self.unfold(y_reshape[:, i: i + 1, :, :])
            unfold_feamap = self.resolution_trans(unfold_feamap.transpose(-1, -2)).transpose(-1, -2)  # B, d*d, DHW/d/d

            # AdaptivePooling
            unfold_feamap = self.pool(unfold_feamap)  # B, d*d, d*d

            att = torch.matmul(unfold_img, unfold_feamap)  # B, DHW/d/d, d*d
            # att = torch.matmul(unfold_img, unfold_feamap)  # B, DHW/d/d, DHW/d/d

            att = fold_layer(att.transpose(-1, -2))

            # att = torch.unsqueeze(att, 1)

            attentions.append(att)

        attentions = torch.cat((attentions), dim=1)  # B, C, DHW/d/d, d*d

        attentions = attentions.reshape(1, C, D, H, W)

        return attentions


class Cross_head(nn.Module):
    def __init__(self, in_dim, out_dim, patch_size=9):
        super().__init__()
        self.patch_size = patch_size

        self.unfold = nn.Unfold(kernel_size=(self.patch_size, self.patch_size),
                                stride=(self.patch_size, self.patch_size))

        self.activation = nn.LeakyReLU(0.2)

        self.conv_img = nn.Sequential(
            nn.Conv3d(in_dim, out_dim, kernel_size=(1, 1, 1), stride=1)
        )

        self.conv_feamap = nn.Sequential(
            nn.Conv3d(in_dim, out_dim, kernel_size=(1, 1, 1), stride=1)
        )

    def forward(self, x, attentions):
        # attention: [B, C, DHW/d/d, DHW/d/d]
        # x needs [B,C DHW/d/d, d*d]

        # step 1. adjust the channel of x
        x = self.conv_img(x)

        # reshape x to [B, C, D, HW]
        x = x.reshape(1, x.size()[1], x.size()[2], x.size()[3] * x.size()[4])

        fold_layer = torch.nn.Fold(output_size=(x.size()[-2], x.size()[-1]),
                                   kernel_size=(self.patch_size, self.patch_size),
                                   stride=(self.patch_size, self.patch_size))

        correction = []

        for i in range(x.size()[1]):
            non_zeros = torch.unsqueeze(torch.count_nonzero(attentions[:, i:i + 1, :, :], dim=-1) + 0.00001, dim=-1)

            decoder_fea = torch.unsqueeze(self.unfold(x[:, i:i + 1, :, :]), dim=1).transpose(-1, -2)  # B, d*d, DHW/d/d

            # [B,C, d*d, DHW/d/d] multi [B, C, DHW/d/d, d*d]

            # att = torch.matmul(attentions[:, i:i + 1, :, :] / non_zeros, decoder_fea)

            att = decoder_fea + attentions[:, i:i + 1, :, :] / non_zeros

            att = torch.squeeze(att, dim=1)

            att = fold_layer(att.transpose(-1, -2))  # [B C HW, D]

            correction.append(att)

        correction = torch.cat(correction, dim=1)

        x = correction * x + x

        x = self.activation(x)

        return x


class Cross_head_bak(nn.Module):
    def __init__(self, in_dim, out_dim, patch_size=9):
        super().__init__()
        self.patch_size = patch_size

        self.unfold = nn.Unfold(kernel_size=(self.patch_size, self.patch_size),
                                stride=(self.patch_size, self.patch_size))

        self.activation = nn.LeakyReLU(0.2)

        self.conv_img = nn.Sequential(
            nn.Conv3d(in_dim, out_dim, kernel_size=(1, 1, 1), stride=1)
        )

        self.conv_feamap = nn.Sequential(
            nn.Conv3d(in_dim, out_dim, kernel_size=(1, 1, 1), stride=1)
        )

    def forward(self, x, attentions):
        # attention: [B, C, DHW/d/d, DHW/d/d]
        # x needs [B,C DHW/d/d, d*d]

        # step 1. adjust the channel of x
        x = self.conv_img(x)

        # reshape x to [B, C, D, HW]
        x = x.reshape(1, x.size()[1], x.size()[2], x.size()[3] * x.size()[4])

        fold_layer = torch.nn.Fold(output_size=(x.size()[-2], x.size()[-1]),
                                   kernel_size=(self.patch_size, self.patch_size),
                                   stride=(self.patch_size, self.patch_size))

        correction = []

        for i in range(x.size()[1]):
            non_zeros = torch.unsqueeze(torch.count_nonzero(attentions[:, i:i + 1, :, :], dim=-1) + 0.00001, dim=-1)

            att = torch.matmul(attentions[:, i:i + 1, :, :] / non_zeros,
                               torch.unsqueeze(self.unfold(x[:, i:i + 1, :, :]), dim=1).transpose(-1, -2))

            att = torch.squeeze(att, dim=1)

            att = fold_layer(att.transpose(-1, -2))  # [B C HW, D]

            correction.append(att)

        correction = torch.cat(correction, dim=1)

        x = correction * x + x

        x = self.activation(x)

        return x


class SCSEModule(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.cSE = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv3d(in_channels, out_channels, 1),
            nn.LeakyReLU(0.2),
            nn.Conv3d(out_channels, out_channels, 1),
            nn.LeakyReLU(0.2),
        )
        self.sSE = nn.Sequential(nn.Conv3d(in_channels, 1, 1), nn.LeakyReLU(0.2))

        self.activate = nn.LeakyReLU(0.2)

        self.patch_size = 9

    def forward(self, x, att):
        fold_layer = torch.nn.Fold(output_size=(x.size()[-3], x.size()[-1] * x.size()[-2]),
                                   kernel_size=(self.patch_size, self.patch_size),
                                   stride=(self.patch_size, self.patch_size))

        pre = x * self.cSE(x) + x * self.sSE(x)

        att = fold_layer(att.transpose(-1, -2))

        return pre + self.activate(torch.matmul(pre, att))
