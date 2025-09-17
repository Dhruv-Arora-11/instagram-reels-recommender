from sklearn.base import BaseEstimator, TransformerMixin

class GenderTransformer(BaseEstimator, TransformerMixin):
    """
    This is an improved version of the GenderTransformer.
    It uses the efficient .map() function for clarity and performance.
    """
    def fit(self, X, y=None):
        return self
        
    def transform(self, X):
        X_copy = X.copy()
        
        for col in X_copy.columns:
            # Use a dictionary to define the mapping
            gender_map = {'M': 0, 'F': 1}
            X_copy[col] = X_copy[col].map(gender_map)
            
        return X_copy