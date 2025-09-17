from sklearn.preprocessing import LabelEncoder
from sklearn.base import BaseEstimator, TransformerMixin

class SimplifiedLabelEncoder(BaseEstimator, TransformerMixin):
    """
    This class converts text categories to numbers.
    It handles new, unseen categories by assigning them -1.
    The code is written with simple loops for clarity.
    """
    def __init__(self):
        self.encoders = {}

    def fit(self, X, y=None):
        for column_name in X.columns:
            encoder = LabelEncoder()
            # Teach the encoder the mapping from text to numbers
            encoder.fit(X[column_name].astype(str).unique())
            # Save the trained encoder for later
            self.encoders[column_name] = encoder
            
        return self

    def transform(self, X):
        X_copy = X.copy()
        for column_name in X.columns:
            # Get the encoder that we trained for this column
            encoder = self.encoders[column_name]
            known_categories = list(encoder.classes_)
            
            #to hold our new, numerical values
            new_values = []
            
            # Go through each value in the column, one by one
            for value in X_copy[column_name]:
                # Check if the current value is one the encoder learned
                if value in known_categories:
                    # If yes, transform it to its corresponding number
                    # We use .transform([value])[0] to get the single number out
                    encoded_value = encoder.transform([value])[0]
                    new_values.append(encoded_value)
                else:
                    # If it's a new, unknown category, assign -1
                    new_values.append(-1)
            
            # Replace the old column with our new list of numbers
            X_copy[column_name] = new_values
            
        return X_copy
