from sklearn.metrics import pairwise_distances
import numpy as np

def predict_with_fallback(preprocessor_pipeline, centroids_df , fav_clusters_latest, raw_point):
    
    # CORRECT FILTERING SYNTAX (Filters by Index, not Column)
    centroids_df = centroids_df[centroids_df.index.isin(fav_clusters_latest)]
    
    # Transform the raw input point using the provided preprocessor pipeline
    if preprocessor_pipeline is None:
        raise ValueError("preprocessor_pipeline must be provided to transform raw_point")
    transformed_point = preprocessor_pipeline.transform([raw_point])
    
    distances = pairwise_distances(transformed_point, centroids_df.values)
    
    # Find the index of the centroid with the minimum distance
    closest_centroid_index = np.argmin(distances)
    # Get the actual cluster label from the centroid DataFrame's index
    fallback_label = centroids_df.index[closest_centroid_index]
    return fallback_label