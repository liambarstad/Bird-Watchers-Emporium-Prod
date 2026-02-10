from typing import (
    Callable,
    Annotated,
)

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from neo4j import Driver

from state import Neo4jState
from utils.embedding_client import EmbeddingClient
from utils.neo4j_results import Neo4jQueryStep, ResultIds


FORMAT_BIRD_FACTS_FROM_SCORE_QUERY = '''
	WITH b, f, score
	ORDER BY b, score DESC // order by fact relevance within each bird

	WITH b, collect(DISTINCT {
		factId: elementId(f), 
		title: f.title, 
		score: score, 
		text: f.text
	}) AS facts

	WITH b, facts
	OPTIONAL MATCH (b)-[:HAS_FACT]->(f_extra)
	WHERE elementId(f_extra) IN $factIds
	WITH b, facts, collect(DISTINCT {
		factId: elementId(f_extra),
		title: f_extra.title,
		score: null,
		text: f_extra.text
	}) AS extraFacts
	WITH b, facts + extraFacts AS facts

	OPTIONAL MATCH (b)-[:HAS_IMAGE]->(i_extra)
	WHERE elementId(i_extra) IN $imageIds
	WITH b, facts, collect(DISTINCT {
		imageId: elementId(i_extra),
		url: i_extra.url,
		score: null
	}) AS images

	WHERE size(facts) > 0 // no birds without facts
	WITH b, facts, images, rand() AS rnd
	ORDER BY rnd // order birds randomly

	WITH collect(DISTINCT {
		birdId: elementId(b),
		name: b.name,
		family: b.family,
		order: b.order,
		genus: b.genus,
		species: b.species,
		facts: facts,
		images: images,
		continents: [ (b)-[:IN_CONTINENT]->(c) | {name: c.name} ],
		countries: [ (b)-[:IN_COUNTRY]->(co) | {name: co.name} ],
		regions: [ (b)-[:IN_REGION]->(r) | {name: r.name} ]
	}) AS birdItems

	WITH
		birdItems,
		[item IN birdItems | item.birdId] AS birdIds,
		reduce(factIds = [], item IN birdItems |
			reduce(acc = factIds, f IN item.facts |
				CASE WHEN f.factId IN acc THEN acc ELSE acc + f.factId END
			)
		) AS factIds,
		reduce(imageIds = [], item IN birdItems |
			reduce(acc = imageIds, i IN item.images |
				CASE WHEN i.imageId IN acc THEN acc ELSE acc + i.imageId END
			)
		) AS imageIds

	RETURN {
		birdIds: birdIds,
		factIds: factIds,
		imageIds: imageIds,
		sample: birdItems[0..$sample_size]
	} AS result;
'''

FORMAT_BIRD_IMAGES_FROM_SCORE_QUERY = '''
	WITH b, i, score
	ORDER BY b, score DESC // order by image relevance within each bird

	WITH b, collect(DISTINCT {
		imageId: elementId(i), 
		url: i.url, 
		score: score
	}) AS images

	WITH b, images
	OPTIONAL MATCH (b)-[:HAS_IMAGE]->(i_extra)
	WHERE elementId(i_extra) IN $imageIds
	WITH b, images, collect(DISTINCT {
		imageId: elementId(i_extra),
		url: i_extra.url,
		score: null
	}) AS extraImages
	WITH b, images + extraImages AS images

	OPTIONAL MATCH (b)-[:HAS_FACT]->(f_extra)
	WHERE elementId(f_extra) IN $factIds
	WITH b, images, collect(DISTINCT {
		factId: elementId(f_extra),
		title: f_extra.title,
		score: null,
		text: f_extra.text
	}) AS facts

	WHERE size(images) > 0 // no birds without images
	WITH b, images, facts, rand() AS rnd
	ORDER BY rnd // order birds randomly

	WITH collect(DISTINCT {
		birdId: elementId(b),
		name: b.name,
		family: b.family,
		order: b.order,
		genus: b.genus,
		species: b.species,
		images: images,
		facts: facts,
		continents: [ (b)-[:IN_CONTINENT]->(c) | {name: c.name} ],
		countries: [ (b)-[:IN_COUNTRY]->(co) | {name: co.name} ],
		regions: [ (b)-[:IN_REGION]->(r) | {name: r.name} ]
	}) AS birdItems

	WITH
		birdItems,
		[item IN birdItems | item.birdId] AS birdIds,
		reduce(factIds = [], item IN birdItems |
			reduce(acc = factIds, f IN item.facts |
				CASE WHEN f.factId IN acc THEN acc ELSE acc + f.factId END
			)
		) AS factIds,
		reduce(imageIds = [], item IN birdItems |
			reduce(acc = imageIds, i IN item.images |
				CASE WHEN i.imageId IN acc THEN acc ELSE acc + i.imageId END
			)
		) AS imageIds

	RETURN {
		birdIds: birdIds,
		factIds: factIds,
		imageIds: imageIds,
		sample: birdItems[0..$sample_size]
	} AS result;
'''

FORMAT_BIRD_DETAILS_QUERY = '''
	WITH b
	OPTIONAL MATCH (b)-[:HAS_FACT]->(f)
	WITH b, collect(DISTINCT f) AS factNodes
	WITH b, [f IN factNodes WHERE f IS NOT NULL | {
		factId: elementId(f),
		title: f.title,
		score: null,
		text: f.text
	}] AS facts

	OPTIONAL MATCH (b)-[:HAS_IMAGE]->(i)
	WITH b, facts, collect(DISTINCT i) AS imageNodes
	WITH DISTINCT b, facts, imageNodes
	WITH b, facts, [i IN imageNodes WHERE i IS NOT NULL | {
		imageId: elementId(i),
		url: i.url,
		score: null
	}] AS images

	WITH collect(DISTINCT {
		birdId: elementId(b),
		name: b.name,
		family: b.family,
		order: b.order,
		genus: b.genus,
		species: b.species,
		facts: facts,
		images: images,
		continents: [ (b)-[:IN_CONTINENT]->(c) | {name: c.name} ],
		countries: [ (b)-[:IN_COUNTRY]->(co) | {name: co.name} ],
		regions: [ (b)-[:IN_REGION]->(r) | {name: r.name} ]
	}) AS birdItems

	WITH
		birdItems,
		[item IN birdItems | item.birdId] AS birdIds,
		reduce(factIds = [], item IN birdItems |
			reduce(acc = factIds, f IN item.facts |
				CASE WHEN f.factId IN acc THEN acc ELSE acc + f.factId END
			)
		) AS factIds,
		reduce(imageIds = [], item IN birdItems |
			reduce(acc = imageIds, i IN item.images |
				CASE WHEN i.imageId IN acc THEN acc ELSE acc + i.imageId END
			)
		) AS imageIds

	RETURN {
		birdIds: birdIds,
		factIds: factIds,
		imageIds: imageIds,
		sample: birdItems[0..$sample_size]
	} AS result;
'''


def create_lexical_search_tool(
	neo4j_driver: Driver, 
	db_name: str,
) -> Callable:

	@tool
	def lexical_search(
    	keyword: str, 
     	state: Annotated[Neo4jState, InjectedState],
		sample_size: int = 5,
		builds_off_previous_step: bool = True,
		step_description: str = 'Searching by keyword...',
    ):
		'''
		Exact keyword search for bird facts in the database.
		Args:
			keyword: The keyword to search for in the bird facts.
			sample_size: The number of samples to see complete information for. This will not affect the number of results returned. (defaults to 5)
			builds_off_previous_step: Whether to filter the previous step's results (True) or start from scratch (False). (defaults to True)
			step_description: A brief user-facing description of what this step is trying to do.
		'''

		prev_results = state.neo4j_results

		prev_ids = prev_results.steps[-1].result_ids \
			if prev_results.steps and builds_off_previous_step \
			else ResultIds()

		if len(prev_results.steps) == 0:
			builds_off_previous_step = False

		with neo4j_driver.session(database=db_name) as session:
			bird_matching_query = '''
				UNWIND $birdIds AS bid
				MATCH (b:Bird) WHERE elementId(b) = bid

				CALL {
					WITH b
					CALL db.index.fulltext.queryNodes("fact_text_ft", $keyword)
					YIELD node AS f, score
					MATCH (b)-[:HAS_FACT]->(f)
					RETURN b, f, score
				}
			''' if builds_off_previous_step else '''
				CALL db.index.fulltext.queryNodes("fact_text_ft", $keyword)
				YIELD node as f, score
				ORDER BY score ASC
				MATCH (b:Bird)-[:HAS_FACT]->(f)
			'''

			result = session.execute_read(
				lambda tx: tx.run(bird_matching_query + FORMAT_BIRD_FACTS_FROM_SCORE_QUERY,
					keyword=keyword,
					sample_size=sample_size,
					birdIds=prev_ids.bird_ids,
					factIds=prev_ids.fact_ids,
					imageIds=prev_ids.image_ids,
				).single()['result']
			)

			new_step = Neo4jQueryStep(
				description=f'Keyword search for "{keyword}"',
				result_ids=ResultIds(
					bird_ids=result.get('birdIds', []),
					fact_ids=result.get('factIds', []),
					image_ids=result.get('imageIds', []),
				),
				result_sample=result['sample']
			)

			state.neo4j_results.steps.append(new_step)

			return {
				'results_count': len(result.get('birdIds', [])),
				'sample': result['sample']
			}

	return lexical_search


def create_semantic_search_tool(
	neo4j_driver: Driver, 
	db_name: str, 
	embedding_client: EmbeddingClient,
	min_score: float = 0.0,
) -> Callable:

	@tool
	def semantic_search(
    	query: str, 
     	state: Annotated[Neo4jState, InjectedState],
		sample_size: int = 5,
		builds_off_previous_step: bool = True,
		step_description: str = 'Searching by meaning...',
    ):
		'''
		Semantic search for bird facts in the database. Fuzzily matches the query to similar text.
		Args:
			query: The query to search for in the bird facts.
			sample_size: The number of samples to see complete information for. This will not affect the number of results returned. (defaults to 5)
			builds_off_previous_step: Whether to filter the previous step's results (True) or start from scratch (False). (defaults to True)
			step_description: A brief user-facing description of what this step is trying to do.
		'''
		prev_results = state.neo4j_results

		prev_ids = prev_results.steps[-1].result_ids \
			if prev_results.steps and builds_off_previous_step \
			else ResultIds()

		if len(prev_results.steps) == 0:
			builds_off_previous_step = False

		embeddings = embedding_client.embed_texts([query])

		with neo4j_driver.session(database=db_name) as session:
			bird_matching_query = '''
				UNWIND $birdIds AS bid
				MATCH (b:Bird) WHERE elementId(b) = bid

				CALL {
					WITH b
					CALL db.index.vector.queryNodes("facts_embedding_idx", $embeddings)
					YIELD node AS f, score
					WHERE score >= $min_score
					MATCH (b)-[:HAS_FACT]->(f)
					RETURN b, f, score
				}
			''' if builds_off_previous_step else '''
				CALL db.index.vector.queryNodes("facts_embedding_idx", $embeddings)
				YIELD node as f, score
				WHERE score >= $min_score
				ORDER BY score DESC
				MATCH (b:Bird)-[:HAS_FACT]->(f)
			'''

			result = session.execute_read(
				lambda tx: tx.run(bird_matching_query + FORMAT_BIRD_FACTS_FROM_SCORE_QUERY,
					embeddings=embeddings,
					sample_size=sample_size,
					min_score=min_score,
					birdIds=prev_ids.bird_ids,
					factIds=prev_ids.fact_ids,
					imageIds=prev_ids.image_ids,
				).single()['result']
			)

			new_step = Neo4jQueryStep(
				description=f'Semantic search for "{query}"',
				result_ids=ResultIds(
					bird_ids=result.get('birdIds', []),
					fact_ids=result.get('factIds', []),
					image_ids=result.get('imageIds', []),
				),
				result_sample=result['sample']
			)

			state.neo4j_results.steps.append(new_step)

			return {
				'results_count': len(result.get('birdIds', [])),
				'sample': result['sample']
			}

	return semantic_search


def create_visual_search_tool(
	neo4j_driver: Driver, 
	db_name: str, 
	embedding_client: EmbeddingClient,
	min_score: float = 0.0,
) -> Callable:

	@tool
	def visual_search(
     	description: str, 
      	state: Annotated[Neo4jState, InjectedState],
		sample_size: int = 5,
		builds_off_previous_step: bool = True,
		step_description: str = 'Searching by visual description...',
    ):
		'''
		Search images of birds by their description.
		Args:
			description: The description of the bird to search for.
			sample_size: The number of samples to see complete information for. This will not affect the number of results returned. (defaults to 5)
			builds_off_previous_step: Whether to filter the previous step's results (True) or start from scratch (False). (defaults to True)
			step_description: A brief user-facing description of what this step is trying to do.
		'''

		prev_results = state.neo4j_results

		prev_ids = prev_results.steps[-1].result_ids \
			if prev_results.steps and builds_off_previous_step \
			else ResultIds()

		if len(prev_results.steps) == 0:
			builds_off_previous_step = False

		embeddings = embedding_client.embed_texts([description])
		
		with neo4j_driver.session(database=db_name) as session:
			bird_matching_query = '''
				UNWIND $birdIds AS bid
				MATCH (b:Bird) WHERE elementId(b) = bid

				CALL {
					WITH b
					CALL db.index.vector.queryNodes("image_embedding_idx", $embeddings)
					YIELD node AS i, score
					WHERE score >= $min_score
					MATCH (b)-[:HAS_IMAGE]->(i)
					RETURN b, i, score
				}
			''' if builds_off_previous_step else '''
				CALL db.index.vector.queryNodes("image_embedding_idx", $embeddings)
				YIELD node as i, score
				WHERE score >= $min_score
				ORDER BY score DESC
				MATCH (b:Bird)-[:HAS_IMAGE]->(i)
			'''

			result = session.execute_read(
				lambda tx: tx.run(bird_matching_query + FORMAT_BIRD_IMAGES_FROM_SCORE_QUERY,
					embeddings=embeddings,
					sample_size=sample_size,
					min_score=min_score,
					birdIds=prev_ids.bird_ids,
					factIds=prev_ids.fact_ids,
					imageIds=prev_ids.image_ids,
				).single()['result']
			)

			new_step = Neo4jQueryStep(
				description=f'Visual image search for "{description}"',
				result_ids=ResultIds(
					bird_ids=result.get('birdIds', []),
					fact_ids=result.get('factIds', []),
					image_ids=result.get('imageIds', []),
				),
				result_sample=result['sample']
			)

			state.neo4j_results.steps.append(new_step)

			return {
				'results_count': len(result.get('birdIds', [])),
				'sample': result['sample']
			}

	return visual_search


def create_continent_search_tool(
	neo4j_driver: Driver, 
	db_name: str,
) -> Callable:

	@tool
	def continent_search(
    	continents: list[str], 
     	state: Annotated[Neo4jState, InjectedState],
		sample_size: int = 5,
		builds_off_previous_step: bool = True,
		step_description: str = 'Searching by continent...',
    ):
		'''
		Search birds by continent name.
		Args:
			continents: List of continent names to search for.
			sample_size: The number of samples to see complete information for. This will not affect the number of results returned. (defaults to 5)
			builds_off_previous_step: Whether to filter the previous step's results (True) or start from scratch (False). (defaults to True)
			step_description: A brief user-facing description of what this step is trying to do.
		'''
		prev_results = state.neo4j_results

		prev_ids = prev_results.steps[-1].result_ids \
			if prev_results.steps and builds_off_previous_step \
			else ResultIds()

		if len(prev_results.steps) == 0:
			builds_off_previous_step = False

		with neo4j_driver.session(database=db_name) as session:
			bird_matching_query = '''
				UNWIND $birdIds AS bid
				MATCH (b:Bird) WHERE elementId(b) = bid
				MATCH (b)-[:IN_CONTINENT]->(c:Continent)
				WHERE c.name IN $continents
			''' if builds_off_previous_step else '''
				MATCH (b:Bird)-[:IN_CONTINENT]->(c:Continent)
				WHERE c.name IN $continents
			'''

			result = session.execute_read(
				lambda tx: tx.run(bird_matching_query + FORMAT_BIRD_DETAILS_QUERY,
					continents=continents,
					sample_size=sample_size,
					birdIds=prev_ids.bird_ids,
				).single()['result']
			)

			new_step = Neo4jQueryStep(
				description=f'Continent search for {continents}',
				result_ids=ResultIds(
					bird_ids=result.get('birdIds', []),
					fact_ids=result.get('factIds', []),
					image_ids=result.get('imageIds', []),
				),
				result_sample=result['sample']
			)

			state.neo4j_results.steps.append(new_step)

			return {
				'results_count': len(result.get('birdIds', [])),
				'sample': result['sample']
			}

	return continent_search


def create_country_search_tool(
	neo4j_driver: Driver, 
	db_name: str,
) -> Callable:

	@tool
	def country_search(
    	countries: list[str], 
     	state: Annotated[Neo4jState, InjectedState],
		sample_size: int = 5,
		builds_off_previous_step: bool = True,
		step_description: str = 'Searching by country...',
    ):
		'''
		Search birds by country name.
		Args:
			countries: List of country names to search for.
			sample_size: The number of samples to see complete information for. This will not affect the number of results returned. (defaults to 5)
			builds_off_previous_step: Whether to filter the previous step's results (True) or start from scratch (False). (defaults to True)
			step_description: A brief user-facing description of what this step is trying to do.
		'''
		prev_results = state.neo4j_results

		prev_ids = prev_results.steps[-1].result_ids \
			if prev_results.steps and builds_off_previous_step \
			else ResultIds()

		if len(prev_results.steps) == 0:
			builds_off_previous_step = False

		with neo4j_driver.session(database=db_name) as session:
			bird_matching_query = '''
				UNWIND $birdIds AS bid
				MATCH (b:Bird) WHERE elementId(b) = bid
				MATCH (b)-[:IN_COUNTRY]->(c:Country)
				WHERE c.name IN $countries
			''' if builds_off_previous_step else '''
				MATCH (b:Bird)-[:IN_COUNTRY]->(c:Country)
				WHERE c.name IN $countries
			'''

			result = session.execute_read(
				lambda tx: tx.run(bird_matching_query + FORMAT_BIRD_DETAILS_QUERY,
					countries=countries,
					sample_size=sample_size,
					birdIds=prev_ids.bird_ids,
				).single()['result']
			)

			new_step = Neo4jQueryStep(
				description=f'Country search for {countries}',
				result_ids=ResultIds(
					bird_ids=result.get('birdIds', []),
					fact_ids=result.get('factIds', []),
					image_ids=result.get('imageIds', []),
				),
				result_sample=result['sample']
			)

			state.neo4j_results.steps.append(new_step)

			return {
				'results_count': len(result.get('birdIds', [])),
				'sample': result['sample']
			}

	return country_search


def create_region_search_tool(
	neo4j_driver: Driver, 
	db_name: str,
) -> Callable:

	@tool
	def region_search(
    	regions: list[str], 
     	state: Annotated[Neo4jState, InjectedState],
		sample_size: int = 5,
		builds_off_previous_step: bool = True,
		step_description: str = 'Searching by region...',
    ):
		'''
		Search birds by region name.
		Args:
			regions: List of region names to search for.
			sample_size: The number of samples to see complete information for. This will not affect the number of results returned. (defaults to 5)
			builds_off_previous_step: Whether to filter the previous step's results (True) or start from scratch (False). (defaults to True)
			step_description: A brief user-facing description of what this step is trying to do.
		'''
		prev_results = state.neo4j_results

		prev_ids = prev_results.steps[-1].result_ids \
			if prev_results.steps and builds_off_previous_step \
			else ResultIds()

		if len(prev_results.steps) == 0:
			builds_off_previous_step = False

		with neo4j_driver.session(database=db_name) as session:
			bird_matching_query = '''
				UNWIND $birdIds AS bid
				MATCH (b:Bird) WHERE elementId(b) = bid
				MATCH (b)-[:IN_REGION]->(r:Region)
				WHERE r.name IN $regions
			''' if builds_off_previous_step else '''
				MATCH (b:Bird)-[:IN_REGION]->(r:Region)
				WHERE r.name IN $regions
			'''

			result = session.execute_read(
				lambda tx: tx.run(bird_matching_query + FORMAT_BIRD_DETAILS_QUERY,
					regions=regions,
					sample_size=sample_size,
					birdIds=prev_ids.bird_ids,
				).single()['result']
			)

			new_step = Neo4jQueryStep(
				description=f'Region search for {regions}',
				result_ids=ResultIds(
					bird_ids=result.get('birdIds', []),
					fact_ids=result.get('factIds', []),
					image_ids=result.get('imageIds', []),
				),
				result_sample=result['sample']
			)

			state.neo4j_results.steps.append(new_step)

			return {
				'results_count': len(result.get('birdIds', [])),
				'sample': result['sample']
			}

	return region_search


def create_neo4j_tools(
	neo4j_driver: Driver, 
	db_name: str,
	embedding_client: EmbeddingClient
) -> list[Callable]:
	return [
		create_lexical_search_tool(neo4j_driver, db_name),
		create_semantic_search_tool(neo4j_driver, db_name, embedding_client),
		create_visual_search_tool(neo4j_driver, db_name, embedding_client),
		create_continent_search_tool(neo4j_driver, db_name),
		create_country_search_tool(neo4j_driver, db_name),
		create_region_search_tool(neo4j_driver, db_name)
	]