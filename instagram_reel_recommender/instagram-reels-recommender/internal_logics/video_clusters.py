def makingVideoClusters(dbscan_sample_raw):
    # Step 6: Create the final mapping DataFrame with only the essential columns
    video_cluster_map = dbscan_sample_raw[['pid', 'dbscan_cluster_label']]
    # Step 7: Save this mapping to the final CSV file
    video_cluster_map.to_csv("video_clusters.csv", index=False)
    print("\nSuccessfully created 'video_clusters.csv'!")
    print("Here's a preview:")
    print(video_cluster_map.head())
    
    return video_cluster_map