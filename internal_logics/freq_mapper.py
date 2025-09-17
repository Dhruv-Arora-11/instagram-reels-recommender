from sklearn.base import BaseEstimator, TransformerMixin

class SimplifiedFrequencyMapper(BaseEstimator, TransformerMixin):
    """
    This class replaces rare categories with a default value.
    The code is written with simple loops for clarity.
    """
    def __init__(self, threshold=40):
        self.threshold = threshold
        self.common_categories = {}

    def fit(self, X, y=None):   #for learning purpose
        for column_name in X.columns:
            category_counts = X[column_name].value_counts()
            frequent_ones = category_counts[category_counts >= self.threshold]
            self.common_categories[column_name] = list(frequent_ones.index)
        return self

    def transform(self, X):     #actual writing to data
        X_copy = X.copy()
        for column_name in X.columns:
            # Get the list of common categories that we learned during .fit()
            learned_common_list = self.common_categories[column_name]
            
            new_values = []
            
            for value in X_copy[column_name]:
                # Check if the current value is in our list of common ones
                if value in learned_common_list:
                    # If it is, keep the original value
                    new_values.append(value)
                else:
                    # If it's not common, replace it with our default value
                    new_values.append(str(self.threshold))
            # Replace the old column with our new list of processed values
            X_copy[column_name] = new_values
            
        return X_copy