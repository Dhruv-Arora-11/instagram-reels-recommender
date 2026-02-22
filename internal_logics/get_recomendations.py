def get_recommendations(target_video_pid, target_cluster_label, all_videos_df, video_cluster_map, top_n=5):
    # Find all videos belonging to the same cluster
    similar_video_pids = video_cluster_map[video_cluster_map['dbscan_cluster_label'] == target_cluster_label]['pid']

    # Get the full details of these similar videos from the original dataframe
    similar_videos_df = all_videos_df[all_videos_df['pid'].isin(similar_video_pids)]
    
    # Exclude the original video itself from the recommendations
    similar_videos_df = similar_videos_df[similar_videos_df['pid'] != target_video_pid]

    # Rank these similar videos. Let's use 'watch_time' as the ranking metric.
    recommendations = similar_videos_df.sort_values(by='watch_time', ascending=False)

    return recommendations.head(top_n)