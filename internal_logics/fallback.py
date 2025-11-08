from sklearn.metrics import pairwise_distances
import numpy as np

def predict_with_fallback(preprocessor_pipeline, centroids_df , fav_clusters_latest):
    
    # CORRECT FILTERING SYNTAX (Filters by Index, not Column)
    centroids_df = centroids_df[centroids_df.index.isin(fav_clusters_latest)]
    
    distances = pairwise_distances(transformed_point, centroids_df.values)
    
    # Find the index of the centroid with the minimum distance
    closest_centroid_index = np.argmin(distances)
    # Get the actual cluster label from the centroid DataFrame's index
    fallback_label = centroids_df.index[closest_centroid_index]
    return fallback_label