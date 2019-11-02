import torch
import pickle
import numpy as np
from evaluation import *
from functions import *
import torch.optim as optim
from torch.utils.data import TensorDataset
from Models.AutoEncoder import AutoEncoder
from Models.AutoEncoderEx import AutoEncoderEx
from Models.UNet import UNet

if __name__ == "__main__":
    models = [AutoEncoder, AutoEncoderEx, UNet]
    learning_rates = [1e-3, 1e-4, 1e-5]
    kernel_sizes = [3, 5, 7]
    filters = [[16, 32, 64], [8, 16, 32, 32], [8, 16, 16, 32, 32]]
    batch_norm = [False, True]
    weight_nrom = [False, True]

    # Loading dataset
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    x = pickle.load(open("./Xs.pkl", "rb"))
    y = pickle.load(open("./Ys.pkl", "rb"))
    x = torch.FloatTensor(x)
    y = torch.FloatTensor(y)
    # Shifting dimensions
    x, y = x.permute(0, 3, 1, 2), y.permute(0, 3, 1, 2)
    # Removing channel 1 in input channels
    x = torch.cat((x[:, 0:1, :, :], x[:, 2:, :, :]), dim=1)
    # Adding binary channel to describe the shape of object
    mask = (1 - torch.isnan(x[:, 2:, :, :]).type(torch.float))
    x = torch.cat([x, mask], dim=1)
    x[torch.isnan(x)] = 0
    y[torch.isnan(y)] = 0
    channels_weights = torch.sqrt(torch.mean(y.permute(0, 2, 3, 1).view(-1, y.shape[1]) ** 2, dim=0)).view(1, -1, 1, 1).to(device)
    print(channels_weights)
    print(x.shape)
    print(y.shape)
    # Shuffling the dataset
    x, y = shuffle_tensors(x, y)
    # Spliting dataset into 70% train and 30% test
    train_data, test_data = split_tensors(x, y, ratio=0.7)
    train_dataset, test_dataset = TensorDataset(*train_data), TensorDataset(*test_data)

    def train_cnnCFD(config):
        print("Evaluating configuration: ")
        print(config)
        torch.manual_seed(0)
        model = config["model"]
        lr = config["lr"]
        kernel_size = config["kernel"]
        filters = config["filters"]
        bn = config["bn"]
        wn = config["wn"]
        model = model(4, 3, filters=filters, kernel_size=kernel_size,
                    batch_norm=bn, weight_norm=wn)
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
        
        def loss_func(model, batch):
            x, y = batch
            output = model(x)
            loss = ((output - y) ** 2) / channels_weights
            return torch.sum(loss), output
        
        # Training model
        best_model, train_metrics, train_loss, test_metrics, test_loss = train_model(model, loss_func, train_dataset, test_dataset, optimizer,
                epochs=1000, batch_size=32, device=device,
                m_mse_name="Total MSE",
                m_mse_on_batch=lambda scope: float(torch.sum((scope["output"] - scope["batch"][1]) ** 2)),
                m_mse_on_epoch=lambda scope: sum(scope["list"]) / len(scope["dataset"]),
                m_ux_name="Ux MSE",
                m_ux_on_batch=lambda scope: float(torch.sum((scope["output"][:,0,:,:] - scope["batch"][1][:,0,:,:]) ** 2)),
                m_ux_on_epoch=lambda scope: sum(scope["list"]) / len(scope["dataset"]),
                m_uy_name="Uy MSE",
                m_uy_on_batch=lambda scope: float(torch.sum((scope["output"][:,1,:,:] - scope["batch"][1][:,1,:,:]) ** 2)),
                m_uy_on_epoch=lambda scope: sum(scope["list"]) / len(scope["dataset"]),
                m_p_name="p MSE",
                m_p_on_batch=lambda scope: float(torch.sum((scope["output"][:,2,:,:] - scope["batch"][1][:,2,:,:]) ** 2)),
                m_p_on_epoch=lambda scope: sum(scope["list"]) / len(scope["dataset"]), patience=25,
                )
        print("Best loss = " + str(test_loss))
        return test_loss
    simulation_id = 0
    best_loss = float("inf")
    best_config = None
    for model in models:
        for kernel in kernel_sizes:
            for filter in filters:
                for bn in batch_norm:
                    for wn in weight_nrom:
                        for lr in learning_rates:
                            config = {
                                "id" : simulation_id,
                                "model" : model,
                                "lr" : lr,
                                "kernel" : kernel,
                                "filters" : filter,
                                "bn" : bn,
                                "wn" : wn,
                            }
                            loss = train_cnnCFD(config)
                            if loss < best_loss:
                                best_loss = loss
                                best_config = config
                            simulation_id += 1
    print("Best configuration: ")
    print(best_config)
    print("Minimum loss = " + str(best_loss))
