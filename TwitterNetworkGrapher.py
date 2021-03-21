# Twitter API playground
# Network graph of Twitter user's friends
# 3/20/2021
# Will Devitt

# # # # # # # # # # # # # # # # # # # # # # # # # # # #

# Structure:
# 1: Imports
# 1a: function definitions (textbook functions at the top)
# 1b: Declarations & Calls (Heap) done in "if name == main" at tail of file

# # # # # # # # # # # # # # # # # # # # # # # # # # # #

# !!! FYI !!!
# I could only write to file by running this script through
# Admin command line.

# # # # # # # # # # # # # # # # # # # # # # # # # # # #

import twitter
import networkx
from matplotlib import pylab
import sys
import time
from urllib.error import URLError
from http.client import BadStatusLine
from functools import partial
from sys import maxsize as maxint

# # # # # # # # # # # # # # # # # # # # # # # # # # # #

# Auth / Login function (my credentials)
def oauth_login():
    CONSUMER_KEY = ''
    CONSUMER_SECRET = ''
    OAUTH_TOKEN = ''
    OAUTH_TOKEN_SECRET = ''

    auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET,
                               CONSUMER_KEY, CONSUMER_SECRET)

    twitter_api = twitter.Twitter(auth=auth)
    return twitter_api

# Function: makes twitter API requests
def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw):
    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):

        if wait_period > 3600:  # Seconds
            print('Too many retries. Quitting.', file=sys.stderr)
            raise e

        # See https://developer.twitter.com/en/docs/basics/response-codes
        # for common codes

        if e.e.code == 401:
            print('Encountered 401 Error (Not Authorized)', file=sys.stderr)
            return None
        elif e.e.code == 404:
            print('Encountered 404 Error (Not Found)', file=sys.stderr)
            return None
        elif e.e.code == 429:
            print('Encountered 429 Error (Rate Limit Exceeded)', file=sys.stderr)
            if sleep_when_rate_limited:
                print("Retrying in 15 minutes...ZzZ...", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(60 * 15 + 5)
                print('...ZzZ...Awake now and trying again.', file=sys.stderr)
                return 2
            else:
                raise e  # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print('Encountered {0} Error. Retrying in {1} seconds'.format(e.e.code, wait_period), file=sys.stderr)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function

    wait_period = 2
    error_count = 0

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError as e:
            error_count = 0
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("URLError encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise
        except BadStatusLine as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("BadStatusLine encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise

# Function: Get a user profile, format to dictionary
def get_user_profile(twitter_api, screen_names=None, user_ids=None):
    # Must have either screen_name or user_id (logical xor)
    assert (screen_names != None) != (user_ids != None), "Must have screen_names or user_ids, but not both"

    items_to_info = {}

    items = screen_names or user_ids

    while len(items) > 0:

        # Process 100 items at a time per the API specifications for /users/lookup.
        # See http://bit.ly/2Gcjfzr for details.

        items_str = ','.join([str(item) for item in items[:100]])
        items = items[100:]

        if screen_names:
            response = make_twitter_request(twitter_api.users.lookup,
                                            screen_name=items_str)
        else:  # user_ids
            response = make_twitter_request(twitter_api.users.lookup,
                                            user_id=items_str)

        for user_info in response:
            if screen_names:
                items_to_info[user_info['screen_name']] = user_info
            else:  # user_ids
                items_to_info[user_info['id']] = user_info

    return items_to_info

# Function: Get friend + follower ID's, format to lists
def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None,
                              friends_limit=maxint, followers_limit=maxint):
    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None), "Must have screen_name or user_id, but not both"

    # See http://bit.ly/2GcjKJP and http://bit.ly/2rFz90N for details
    # on API parameters

    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids,
                              count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids,
                                count=5000)

    friends_ids, followers_ids = [], []

    for twitter_api_func, limit, ids, label in [
        [get_friends_ids, friends_limit, friends_ids, "friends"],
        [get_followers_ids, followers_limit, followers_ids, "followers"]
    ]:

        if limit == 0: continue

        cursor = -1
        while cursor != 0:

            # Use make_twitter_request via the partially bound callable...
            if screen_name:
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else:  # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']

            print('Fetched {0} total {1} ids for {2}'.format(len(ids), label, (user_id or screen_name)),
                  file=sys.stderr)

            # XXX: You may want to store data during each iteration to provide an
            # an additional layer of protection from exceptional circumstances

            if len(ids) >= limit or response is None:
                break

    # Do something useful with the IDs, like store them to disk...
    return friends_ids[:friends_limit], followers_ids[:followers_limit]

# Function: returns a user's follower count
def get_followers(ids):
    return get_user_profile(twitter_api, user_ids=ids)

# Function: gets list of a user's 5 most popular friends
def get_reciprocal_friends(twitter_api, uid):
    # Friends and followers of user 'uid'
    friends_ids, followers_ids = get_friends_followers_ids(twitter_api,
                                                           user_id=uid,
                                                           friends_limit=5000,
                                                           followers_limit=5000)
    # Intersection of followers and friends (reciprocal friends)
    reciprocal_friends = list(set(friends_ids).intersection(followers_ids))
    reciprocal_followers = get_followers(reciprocal_friends)
    reciprocal_dict = {x: current.get('followers_count') for (x, current) in reciprocal_followers.items()}

    # List of TOP 5, sorted for size, reciprocal friends by uid
    reciprocal_dict = sorted(reciprocal_dict.items(), key=lambda x: x[1], reverse=True)
    output = []
    count = 0
    for key, value in reciprocal_dict:
        count += 1
        output.append(key)
        if count >= 5:
            break
    return output

# Function: Crawls Followers
def crawl_followers(twitter_api, screen_name, total_accts):

# Resolve the ID for screen_name and start working with IDs for consistency
# in storage

    seed_id = int(str(twitter_api.users.show(screen_name=screen_name)['id']))
    out_list = [seed_id]
    # Create graph!
    user_graph = networkx.Graph()
    user_graph.add_node(seed_id)

    # adding edges to graph, each being reciprocal friend
    next_bunch = get_reciprocal_friends(twitter_api, str(seed_id))
    user_graph.add_edges_from([((seed_id),x) for x in next_bunch])

    # Using BFS to expand through the graph
    while user_graph.number_of_nodes() < total_accts:
        curr_bunch = next_bunch
        next_bunch = []
        # (curr_bunch, next_bunch) = (next_bunch, [])
        for uid in curr_bunch:
            user_graph.add_node(uid)
            next_five = get_reciprocal_friends(twitter_api,uid)
            user_graph.add_edges_from([(uid,x) for x in next_five])
            next_bunch = next_bunch + next_five
            if user_graph.number_of_nodes() > total_accts:
                out_list.extend(next_bunch)
                return [out_list,user_graph]
            out_list.extend(next_bunch)

    return [out_list,user_graph]

# # # # # # # # # # # # # # # # # # # # # # # # # # # #

if __name__ == '__main__':
    twitter_api = oauth_login()

    # Call crawler on the starting point of my roommate's Twitter
    # Call with desired levels of depth
    # Change username to customize
    user_name = input("Enter the desired user's name, without any @'s or /'s ")
    try:
        output = crawl_followers(twitter_api, user_name, 100)
    except:
        print("Sanitize the username. Don't include any assingment characters")
    # Create graph, save to file.
    graph = output[1]
    networkx.draw(graph)
    network_fig = pylab.gcf()
    pylab.show()
    pylab.draw()
    network_fig.savefig(r'SocialGraph.png')

    # Create outputs, in console and to file
    num_nodes = graph.number_of_nodes()
    num_edges = graph.number_of_edges()
    avg = networkx.average_shortest_path_length(graph)
    diam = networkx.diameter(graph)

    outfile = open(r'graph_data.txt', 'w')
    outfile.write("Node count: = ")
    outfile.write(str(num_nodes))
    outfile.write("\nEdge count: = ")
    outfile.write(str(num_edges))
    outfile.write("\nAvg distance between nodes = ")
    outfile.write(str(avg))
    outfile.write("\nDiameter of graph = ")
    outfile.write(str(diam))

    print("Node count: = ", num_nodes)
    print("Edge count: = ", num_edges)
    print("Avg distance between nodes = ", avg)
    print("Diameter of graph = ", diam)
    print("Results saved to text file. Graph saved to .png file.")



