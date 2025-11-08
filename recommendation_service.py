import json
import pandas as pd
import pickle
from internal_logics.fallback import predict_with_fallback
from internal_logics.url_for_recomend import url_for_videos
from internal_logics.get_recomendations import get_recommendations

class ReelsRecommendationService:
    
    with open("dbscan_model.pkl", "rb") as f:
        loaded_dbscan_model = pickle.load(f)
    
    cluster_labels = loaded_dbscan_model.labels_

    df_cleaned = pd.read_csv(
        "interaction_filtered.csv", 
        usecols=['pid', 'title', 'author_id', 'watch_time'] 
    )
    
    dbscan_sample_raw = df_cleaned.sample(n=200000, random_state=42)
    dbscan_sample_raw['dbscan_cluster_label'] = cluster_labels
    
    
    df_video_clusters = pd.read_csv("video_clusters.csv")
    
    with open('cluster_centroids.pkl', 'rb') as f:
            cluster_centroids = pickle.load(f)
            
        # to transform the new data
    with open("fitted_preprocessor_5.pkl", "rb") as f:
        full_pipeline = pickle.load(f) 


    def recommendMe(new_data , fav_clusters_latest):
        
        final_cluster = predict_with_fallback(ReelsRecommendationService.full_pipeline , ReelsRecommendationService.cluster_centroids ,fav_clusters_latest)

        recommended_videos = get_recommendations(
            target_video_pid=9999999,
            target_cluster_label=final_cluster,
            all_videos_df=ReelsRecommendationService.dbscan_sample_raw,
            video_cluster_map=ReelsRecommendationService.df_video_clusters
        )
        
        data = {
            'pid': recommended_videos['pid'],
            'title': recommended_videos['title'],
            'author_id': recommended_videos['author_id'],
            'watch_time': recommended_videos['watch_time']
        }
        recommended_videos = pd.DataFrame(data)

        # no duplicated videos
        recommended_videos = recommended_videos.drop_duplicates(subset='pid').reset_index(drop=True)

        all_recomended_videos = url_for_videos(recommended_videos=recommended_videos)