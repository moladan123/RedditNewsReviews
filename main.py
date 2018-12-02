#!/usr/bin/env python
import json
import time
from newspaper import Article
from newspaper import ArticleException
from prawcore import exceptions
import praw
import requests
import tika
import http.client
import json
tika.initVM()
from bs4 import BeautifulSoup
from pprint import pprint
import matplotlib.pyplot as plt

#Don't want to run out that fast
MAX_API_CALLS = 750

MAX_ARTICLES_PER_SUB = 100
ARTICLES_PER_SUB = 25


def get_reddit():
    return praw.Reddit(
        client_id='REDDIT-CLIENTID',
        client_secret='SECRETKEY',
        grant_type='client_credentials',
        user_agent='newsreviews/1.0'
    )


def get_top(subreddit_name):

    article_contents = []

    # Get top n submissions from reddit
    reddit = get_reddit()
    top_subs = reddit.subreddit(subreddit_name).top(limit=MAX_ARTICLES_PER_SUB)

    # Remove those submissions that belongs to reddit
    subs = [sub for sub in top_subs if not sub.domain.startswith('self.')]

    count = ARTICLES_PER_SUB
    while subs and count > 0:
        sub = subs.pop(0)
        article = get_article(sub.url, count)
        if article:
            text = article.text
            article_contents.append(text)
            count -= 1

    return article_contents


def get_article(url, count):
    print('  - Retrieving ' + url, count)
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article
    except ArticleException:
        return None


def parse_article(text):
    print(text)
    soup = BeautifulSoup(text, 'html.parser')

    # find the article title
    h1 = soup.body.find('h1')

    # find the common parent for <h1> and all <p>s.
    root = h1
    while root.name != 'body' and len(root.find_all('p')) < 5:
        root = root.parent

    if len(root.find_all('p')) < 5:
        return None

    # find all the content elements.
    ps = root.find_all(['h2', 'h3', 'h4', 'h5', 'h6', 'p', 'pre'])
    ps.insert(0, h1)
    content = [tag2md(p) for p in ps]

    return {'title': h1.text, 'content': content}


def tag2md(tag):
    if tag.name == 'p':
        return tag.text
    elif tag.name == 'h1':
        return '{tag.text}\n{"=" * len(tag.text)}'
    elif tag.name == 'h2':
        return '{tag.text}\n{"-" * len(tag.text)}'
    elif tag.name in ['h3', 'h4', 'h5', 'h6']:
        return '{"#" * int(tag.name[1:])} {tag.text}'
    elif tag.name == 'pre':
        return '```\n{tag.text}\n```'


# Replace the accessKey string value with your valid access key.
accessKey = 'c7ee1d6c78604175a00ef7787f0026b3'
url = 'westcentralus.api.cognitive.microsoft.com'
path = '/text/analytics/v2.0/Sentiment'


def TextAnalytics(documents):
    headers = {'Ocp-Apim-Subscription-Key': accessKey}
    conn = http.client.HTTPSConnection(url)
    body = json.dumps(documents)
    conn.request("POST", path, body, headers)
    response = conn.getresponse()
    return response.read()


def main():
    subreddits = ['News', 'WorldNews', 'UpliftingNews', 'TrueNews', 'InDepthStories', 'Politics']
    "curl -X POST -H 'User-Agent: newsreviews/1.0' -d grant_type=client_credentials --user '-KwqYZazsaMzQg:Aus3w1126Y8oGMv2nHfFmhNLn98'  https://www.reddit.com/api/v1/access_token"

    texts = dict()

    try:
        for sr in subreddits:
            print('Scraping /r/%s...' % sr)
            texts[sr] = get_top(sr)
    except exceptions.Forbidden:
        print("done!")

    # sanity check, shows the contents of the articles
    for subreddit in texts:
        # make sure that the news articles given to azure are not too long
        texts[subreddit] = [i[:3000] if len(i) > 3000 else i for i in texts[subreddit]]
        # get rid of newline characters
        texts[subreddit] = [i.replace("\n", " ") for i in texts[subreddit]]

        a = texts[subreddit]
        for art in a:

            print(subreddit, art[:40].replace("\n", " "))

    # maps the subreddit to its scored, used later in the script, do not move
    scores = dict()
    for subreddit in subreddits:
        scores[subreddit] = [0.0, 0]


    id = 0
    api_calls = 0
    for subreddit in texts:

        if api_calls == MAX_API_CALLS:
            break
        for article in texts[subreddit]:
            print("parsing " + subreddit + ",", "entry #" + str(id))
            if api_calls == MAX_API_CALLS:
                break
            id += 1
            azure_python_input = {"documents": []}
            azure_python_input["documents"].append(
                {
                    "language": "en",
                    "id": str(subreddit) + "," + str(id),
                    "text": article
                }
            )

            subscription_key = "54207b06a6334837b416443d6b903e80"
            headers = {"Ocp-Apim-Subscription-Key": subscription_key}
            api_calls += 1
            # wait a second since azure complains when we send too many api requests
            time.sleep(1)
            r = requests.post('https://canadacentral.api.cognitive.microsoft.com/text/analytics/v2.0/sentiment',
                              headers=headers, json=azure_python_input)
            output = r.json()

            # add the score for that article

            try:
                subreddit = (output['documents'][0]['id'].split(","))[0]
                score = output['documents'][0]['score']
                if score != 0.5:
                    scores[subreddit][0] += score
                    scores[subreddit][1] += 1
            except:
                print(output)

    pprint(scores)

    # sort by subreddit's average score
    reddits = [(subreddit, scores[subreddit][0] / scores[subreddit][1]) if scores[subreddit][1] else (subreddit, 0.5) for subreddit in subreddits]
    reddits = sorted(reddits, key=lambda d: d[1])

    reddits1 = [i[0] for i in reddits]
    reddits2 = [i[1] for i in reddits]

    plt.bar(reddits1, reddits2)
    plt.show()




if __name__ == '__main__':
    main()
