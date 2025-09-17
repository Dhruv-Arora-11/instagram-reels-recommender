def url_for_videos(recommended_videos):
    BASE_URL = "https://fi.ee.tsinghua.edu.cn/datasets/short-video-dataset/raw_file/"
    for index, row in recommended_videos.iterrows():
        video_pid = row['pid']
        video_title = row['title']
    
        video_url = f"{BASE_URL}{video_pid}.mp4"
    
        print(f"\nRecommendation #{index + 1}:")
        print(f"  Title: {video_title}")
        print(f"  PID: {video_pid}")
        print(f"  Direct Link: {video_url}")
    print("\n---------------------------------------------------------")