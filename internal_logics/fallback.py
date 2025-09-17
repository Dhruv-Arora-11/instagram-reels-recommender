from sklearn.metrics import pairwise_distances
import numpy as np

def predict_with_fallback(new_data_df, preprocessor_pipeline, centroids_df):
    # 1. Transform the new data using the same pipeline as the training data
    transformed_point = preprocessor_pipeline.transform(new_data_df)
    # there is no need of predicting that if the transformed point will fall into some cluster or not because it will almost certainly .
    # because it can not form another cluster just by itself.
    # Calculate distances from the new point to all cluster centroids
    # The .values ensures we are working with NumPy arrays for calculation
    distances = pairwise_distances(transformed_point, centroids_df.values)
    # Find the index of the centroid with the minimum distance
    closest_centroid_index = np.argmin(distances)
    # Get the actual cluster label from the centroid DataFrame's index
    fallback_label = centroids_df.index[closest_centroid_index]
    return fallback_label