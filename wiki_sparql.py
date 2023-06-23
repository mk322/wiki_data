import requests
import json
from collections import defaultdict

# List of top 20 languages
languages = ['en', 'ru', 'id', 'vi', 'fa', 'uk', 'sv', 'th', 'ja', 'de', 'ro', 'hu', 'bg', 'fr', 'fi', 'ko', 'es', 'it', 'pt', 'el']
#languages = ['ko', 'es', 'it', 'pt', 'el']
# Wikidata API endpoint
wikidata_url = 'https://query.wikidata.org/sparql'

# Pageview API endpoint
pageview_url = 'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/all-access/all-agents/{title}/monthly/{start}/{end}'

# Request headers
headers = {
    'User-Agent': 'CoolBot/0.0 (https://example.org/coolbot/; coolbot@example.org)',
    "Accept": "application/json"
}

# Count of each entity
entity_count = {}

all_sitelinks = {}
all_page_titles = {}
# Split languages into smaller batches
batch_size = 5
for i in range(0, len(languages), batch_size):
    batch = languages[i:i + batch_size]

    query = """
            SELECT ?entity """ + " ".join(f"?sitelink_{lang} ?label_{lang}" for lang in batch) + """ WHERE {
                ?entity wdt:P31 wd:Q5 . # instance of human
                """ + "\n".join(f"""
                OPTIONAL {{
                    ?sitelink_{lang} schema:about ?entity ;
                                    schema:isPartOf <https://{lang}.wikipedia.org/> .
                    OPTIONAL {{ ?entity rdfs:label ?label_{lang} . FILTER(LANG(?label_{lang}) = '{lang}') }}
                }}""" for lang in batch) + """
                FILTER(""" + " && ".join(f"(BOUND(?label_{lang}))" for lang in batch) + """)
            }
            LIMIT 500
        """


    # Make the request to the Wikidata API
    response = requests.get(wikidata_url, params={'query': query}, headers=headers)
    response.raise_for_status()

    # Parse the response JSON
    data = response.json()

    # Update the count of each entity
    for result in data['results']['bindings']:
        entity = result['entity']['value']
        entity_count[entity] = entity_count.get(entity, 0) + 1
        entity_sitelinks = {
            lang: result.get(f"sitelink_{lang}", {}).get('value')
            for lang in batch
        }
        page_titles = {
            key: entity_sitelinks[key].split('/')[-1]
                for key in entity_sitelinks}
        if entity in all_page_titles:
            all_page_titles[entity].update(page_titles)
        else:
            all_page_titles[entity] = page_titles

        if entity in all_sitelinks:
            all_sitelinks[entity].update(entity_sitelinks)
        else:
            all_sitelinks[entity] = entity_sitelinks


# Filter entities that are available in all languages
final_entities = [entity_tuple for entity_tuple, count in entity_count.items() if count == len(languages) // batch_size]

all_page_titles = {entity: all_page_titles[entity] for entity in final_entities}
all_sitelinks = {entity: all_sitelinks[entity] for entity in final_entities}

with open('wiki_data/human_terms.json', 'w', encoding='utf-8') as file:
    json.dump(all_page_titles, file, ensure_ascii=False, indent=4)

# Count of page views for each entity
page_views_count = {}

# Retrieve page views for each entity
for entity in all_page_titles:
    # Iterate through languages and retrieve entities

    for lang in languages:
        if lang not in page_views_count:
            page_views_count[lang] = {}

        page_title = all_page_titles[entity][lang]
        
        # Make the request to the Pageview API
        pv_response = requests.get(
            pageview_url.format(project=f"{lang}.wikipedia", title=page_title, start="20230101", end="20230601"),
            headers=headers
        )
        
        # Parse the response JSON and add page views to the count
        pv_data = pv_response.json()
        if 'items' in pv_data:
            for item in pv_data['items']:
                if entity in page_views_count[lang]:
                    page_views_count[lang][entity] += item['views']
                else:
                    page_views_count[lang][entity] = item['views']

# Sort entities by page views
sorted_entities = {lang: sorted(page_views_count[lang], key=lambda x: x[1], reverse=True) for lang in languages}

for lang in languages:
    for i in range(len(sorted_entities[lang])):
        entity = sorted_entities[lang][i]
        sorted_entities[lang][i] = [entity, page_views_count[lang][entity], all_page_titles[entity][lang]]

# Save the results to a local file in JSON format
with open('wiki_data/human_by_page_views.json', 'w', encoding='utf-8') as file:
    json.dump(sorted_entities, file, ensure_ascii=False, indent=4)