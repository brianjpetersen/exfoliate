""" A more realistic example of exfoliate being used for web scraping.

Exfoliate was designed with web scraping in mind.  Although Reddit has an API, the has 
generous robots.txt permissions and also makes for a good demonstration because there are multiple
types of requests that can be made (article lists, links to the articles, comment pages per article,
metadata per article, etc).

Specifically, this script starts at HOST of the Python subreddit landing page and uses an exfoliate
client to GET the content.  Then, it parses the HTML to extract relevant metadata about the list of
articles returned and requests each of those pages.  It also parses out the URL for the next list 
page in the subreddit and repeats this process for 5 list pages.

Aftewards, it waits on the articles to resolve.  At this point, it's up to you to do something
**amazing** with the scraped data.
"""
import time
import lxml.html
import exfoliate
import pprint


START = time.time()
HOST = 'https://www.reddit.com/r/Python/'
MAX_ARTICLE_LISTS = 5 # note, be considerate!


client = exfoliate.Client()


# keep track of the list futures and the article futures separately
list_futures = exfoliate.Futures()
article_futures = exfoliate.Futures()
article_metadata_by_future = {}

# make first request
list_futures.add(client.get(HOST))


for list_future in list_futures:
    if len(list_futures) >= MAX_ARTICLE_LISTS:
        break
    try:
        response = list_future.response()
        response.raise_for_status()
        # parse html and extract article information
        root = lxml.html.fromstring(response.content)
        article_titles = root.xpath('//*[@class="top-matter"]/p[1]/a/text()')
        article_urls = root.xpath('//*[@class="top-matter"]/p[1]/a/@href')
        article_scores = root.xpath('//*[@class="score unvoted"]/text()')
        datetimes_articles_submitted = root.xpath('//*[@class="top-matter"]/p[2]/time/@datetime')
        # iterate over article details, making requests through client and saving futures and metadata
        for details in zip(article_titles, article_urls, datetimes_articles_submitted, article_scores):
            title, url, datetime, score = details
            # skip relative links
            if (url.startswith('http://') or url.startswith('https://')) == False:
                continue
            article_future = client.get(url)
            article_futures.add(article_future)
            article_metadata_by_future[article_future] = {
                'title': title,
                'url': url,
                'when_submitted': datetime,
                'score': score,
            }
        # request next list page
        next_article_list_url, = root.xpath('//*[@class="next-button"]/a/@href')
        list_futures.add(client.get(next_article_list_url))
    except HTTPError:
        # guard against a 429 Too Many Requests rate limiting response and attempt to wait at least
        # 10 seconds or the retry-after header, if supplied
        if response.status_code == 429:
            retry_after = response.headers.get('retry-after', 10)
            time.sleep(int(retry_after) + 1)
        list_futures.add(list_future.retry())
    except:
        # an unknown error has occurred
        list_futures.add(list_future.retry())


articles = []
for article_future in article_futures:
    try:
        response = article_future.response()
        metadata = article_metadata_by_future[article_future]
        metadata['response'] = response
        articles.append(metadata)
    except:
        article_futures.add(article_future.retry())


pprint.pprint(articles)


STOP = time.time()
print(f'{len(articles)} articles scraped in {round(STOP - START, 1)} seconds')
