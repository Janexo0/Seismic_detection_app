import torch
import torch.nn as nn

class CustomEarthquakeModel(nn.Module):
    """Example custom model architecture - replace with your actual model"""
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv1d(1, 32, kernel_size=7, padding=3)
        self.conv2 = nn.Conv1d(32, 64, kernel_size=5, padding=2)
        self.pool = nn.MaxPool1d(2)
        self.fc1 = nn.Linear(64, 128)
        self.fc2 = nn.Linear(128, 3)  # P, S, Noise probabilities
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        
    def forward(self, x):
        # x shape: (batch, 1, length)
        x = self.relu(self.conv1(x))
        x = self.pool(x)
        x = self.relu(self.conv2(x))
        x = self.pool(x)
        
        # Global average pooling
        x = torch.mean(x, dim=2)
        
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        
        return torch.softmax(x, dim=1)