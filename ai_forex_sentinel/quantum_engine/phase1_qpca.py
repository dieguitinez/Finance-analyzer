import numpy as np
import pandas as pd

class QuantumPCA:
    def __init__(self, n_components=2):
        self.n_components = n_components
        self.components = None
        self.mean = None

    def fit_transform(self, df):
        # Extract numerical columns only
        data = df.select_dtypes(include=[np.number]).fillna(0).values
        if data.shape[1] < self.n_components:
            return np.zeros((data.shape[0], self.n_components))
        
        # Center the data
        self.mean = np.mean(data, axis=0)
        centered = data - self.mean
        
        # Covariance matrix approximation
        cov = np.cov(centered, rowvar=False)
        
        # Eigen decomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        
        # Sort eigenvectors by eigenvalues in descending order
        idx = np.argsort(eigenvalues)[::-1]
        self.components = eigenvectors[:, idx[:self.n_components]]
        
        # Project data
        transformed = np.dot(centered, self.components)
        return transformed
