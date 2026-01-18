import torch
import torch.nn as nn

class EventCNN(nn.Module):
    """Pre-trained earthquake detection model"""
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(3, 32, 11, padding=5),
            nn.ReLU(),
            nn.MaxPool1d(4),
            nn.Conv1d(32, 64, 7, padding=3),
            nn.ReLU(),
            nn.MaxPool1d(4),
            nn.Conv1d(64, 128, 5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1)
        )
        self.fc = nn.Linear(128, 1)
    
    def forward(self, x):
        x = self.conv(x)
        x = x.squeeze(-1)
        return torch.sigmoid(self.fc(x))