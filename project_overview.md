Team 90
Members: Matty Maloni, Toni Comer, Shawn Chen
Project Title: PortalPath
Problem: As the college football transfer portal has exploded with NIL, players have no data driven way to identify which programs will best develop their skills. With thousands of transfers annually, decisions are made on perception rather than historical data. 
Motivation: The transfer portal has fundamentally changed college football. Players transfer multiple times, rosters are rebuilt yearly, and careers are significantly altered by moves. However, there is no accessible tool that exists to map outcomes and use them to recommend optimal destinations for specific players,
Features: The problem is solved when a user can input or look up a player profile (position, current program, and key performance stats) and receive a recommended transfer path backed by historical success data, with two algorithms producing comparable, explainable results. The static network map should also clearly show which programs are best and worst destinations for talent. 
Data: CollegeFootballData.com API - free and public, 
Endpoints used: 
Transfer portal entries (2018-2025): player name, origin school, destination school, position
Player stats by season: yards, usage rate, PPA (predicted points added), games started, snap count percentage
Recruiting data: original recruiting star rating per player
Data is structured at the player × season × stat level. With ~2,000 portal entries per year across 7 years and multiple stat categories per player tracked across pre- and post-transfer seasons, this reaches 100k+ rows.
Success delta is computed by comparing a player's composite score the season before and after their transfer. The composite score pulls from PPA, usage rate, games started, and yards per snap (exact weighting refined through experimentation). Players below a minimum games played threshold are excluded. This delta becomes the edge weight in the graph.
Stored locally as: transfers.csv, player_stats.csv, edges.csv
Name normalization applied during cleaning to handle inconsistent formatting across datasets.
Tools: 
C++: core graph structure, Dijkstra's and Bellman-Ford implemented from scratch
Python: data ingestion and cleaning (pandas, requests), success delta computation, visualization (Pyvis or NetworkX + Matplotlib)
File I/O: Python exports edge list, C++ consumes it and returns optimal path
Visuals: 
Static Mode: Full FBS program network. Nodes sized by how often a program is a successful transfer destination. Edges colored green (high success) to red (negative outcome), thickness scaled by transfer volume. Low-sample edges rendered faded and excluded from pathfinding.
Player Mode: User inputs position, current program, and key performance stats. Irrelevant nodes dim. Both algorithms animate side by side. Recommended path highlights with a side panel showing path chosen, runtime comparison, and where the two algorithms diverge.
Player Lookup: Search any player in the dataset by name. Returns their transfer history, origin, destination prog, and optimal path for transferring
Strategy: The graph is represented as a weighted directed adjacency list. Each node is an FBS program. Each edge represents transfers between two programs, weighted by the average success delta of players with a similar profile who made that move. Edges below a minimum transfer threshold (~10) are excluded from pathfinding to prevent small sample sizes from skewing results.
Two algorithms are implemented from scratch in C++:
Dijkstra's: greedy, priority queue based, optimal for positive edge weights
Bellman-Ford: relaxation based, handles negative weights (programs that hurt development), slower but more flexible
Distribution of Responsibility and Roles
Member 1: Data pipeline — API calls, cleaning, name normalization, success delta computation, CSV outputs, player lookup
Member 2: C++ core — graph structure, Dijkstra's and Bellman-Ford implemented from scratch, Python/C++ file I/O interface
Member 3: Python visualization — static network map, player mode, demo video
References
CollegeFootballData.com. (n.d.). College Football Data API. https://collegefootballdata.com
Dijkstra, E. W. (1959). A note on two problems in connexion with graphs. Numerische Mathematik, 1(1), 269–271.
Bellman, R. (1958). On a routing problem. Quarterly of Applied Mathematics, 16(1), 87–90.
Wireframes:


