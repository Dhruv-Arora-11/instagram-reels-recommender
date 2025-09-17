# Short Video Recommendation System

This project is a content-based recommendation system that suggests short videos to users. It leverages unsupervised machine learning to group similar videos into clusters and recommends popular items from a video's own cluster.

---

## 🚀 Key Features

* **Custom Preprocessing Pipeline**: Utilizes custom scikit-learn transformers to handle various data types, including boolean, categorical, and skewed numerical data.
* **Dimensionality Reduction**: Employs Principal Component Analysis (PCA) to reduce the feature space, making the clustering process more efficient.
* **DBSCAN Clustering**: Uses the DBSCAN (Density-Based Spatial Clustering of Applications with Noise) algorithm to identify clusters of similar videos in the reduced feature space.
* **Recommendation Logic**: For any given video, the system identifies its cluster and recommends other highly-rated videos from the same group.

---

## 🛠️ Methodology

The recommendation workflow is as follows:

1.  **Data Preprocessing**: Raw user interaction data is cleaned and processed using a custom pipeline. This includes log transformations for skewed data, frequency-based mapping for rare categories, and label encoding.
2.  **Dimensionality Reduction**: The high-dimensional feature set is reduced to its principal components using PCA, capturing 95% of the variance.
3.  **Clustering**: The transformed, low-dimensional data is fed into a pre-trained DBSCAN model to group videos into clusters.
4.  **Centroid Calculation**: The center (centroid) of each cluster is calculated to represent the "average" video in that group.
5.  **Recommendation**: When a new video's data is provided, it's transformed using the same pipeline. The system then finds the nearest cluster centroid and recommends the top-rated videos from that cluster.


## 📁 Project Structure

* `recomend_reels.ipynb`: The main Jupyter Notebook containing the end-to-end analysis and recommendation logic.
* `internal_logics/`: A directory containing all the modular Python scripts for custom transformers and functions.
* `*.pkl`: Saved (pickled) files for the trained preprocessor pipeline, DBSCAN model, and cluster centroids.
* `*.npy`: Saved NumPy array of the transformed data.
* `*.csv`: The source data and generated cluster mappings.
