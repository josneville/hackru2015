from flask import Flask, request, render_template
from yelpapi import YelpAPI
from py2neo import Graph, Node, Relationship, Rel, Rev
from py2neo.packages.httpstream import http
http.socket_timeout = 9999
import json
import requests

app = Flask(__name__)
graph = Graph("http://neo4j:bananaman@localhost:7474/db/data")
yelp = YelpAPI('yJPSDGnLa0cmp8i5McqgkQ', 'MmRPkj-q_0BBg2TM8Lr3xvBcXi8', 'PuondDF9UNF2Flpdq_FA3j_jnIzoG8ny', 'XqaafOSHDZijNLOweCroHXnjHUQ')
uber_key = '7wEGBplbyDuptVTyrqOyOk0fasOB-Xvd5xYqWN79'

@app.route("/")
def main():
	return render_template('index.html')

@app.route("/test")
def test_page():
	return render_template('test.html')

@app.route("/api/find", methods=["POST"])
def find():
	nodes = []
	location = request.form["location"]
	results = yelp.search_query(term = '', location=location, sort = 2)
	graph.cypher.execute("MATCH (n) OPTIONAL MATCH (n)-[r]-() DELETE n,r")
	businesses = results["businesses"]
	start = Node("Start", name = location, lat=results["region"]["center"]["latitude"], lon=results["region"]["center"]["longitude"], duration = 0)
	graph.create(start)
	for i in range(len(businesses)):
		lat = businesses[i]["location"]["coordinate"]["latitude"]
		lon = businesses[i]["location"]["coordinate"]["longitude"]
		image_url = businesses[i]["image_url"]
		url = businesses[i]["url"]
		name = businesses[i]["name"]
		duration = 60 * 30
		for category in businesses[i]["categories"]:
			if "parks" in category or "landmarks & historical buildings" in category or "restaurants" in category:
				duration = 5400
				break
			if "museums" in category or "shopping" in category or "entertainment" in category:
				duration = 7200
				break
		node = Node("Destination", name = name, lat = lat, lon = lon, image_url = image_url, url = url, duration = duration)
		graph.create(node)
		nodes.append(node)
	for i in range(len(businesses)):
		lat1 = str(results["region"]["center"]["latitude"])
		lon1 = str(results["region"]["center"]["longitude"])
		lat2 = str(businesses[i]["location"]["coordinate"]["latitude"])
		lon2 = str(businesses[i]["location"]["coordinate"]["longitude"])

		url = "https://api.uber.com/v1/estimates/price?start_latitude="+lat1+"&start_longitude="+lon1+"&end_latitude="+lat2+"&end_longitude="+lon2+"&token="+uber_key
		headers = {
			'Authorization': 'Token %s' % uber_key,
      'Content-Type': 'application/json'
		}
		r = requests.get(url, headers=headers)
		relationship = Relationship(start, "Travel", nodes[i], duration=(r.json())["prices"][0]["duration"], cost=(r.json())["prices"][0]["low_estimate"])
		graph.create(relationship)

		for j in range(i+1, len(businesses)):
			lat1 = str(businesses[i]["location"]["coordinate"]["latitude"])
			lon1 = str(businesses[i]["location"]["coordinate"]["longitude"])
			lat2 = str(businesses[j]["location"]["coordinate"]["latitude"])
			lon2 = str(businesses[j]["location"]["coordinate"]["longitude"])

			url = "https://api.uber.com/v1/estimates/price?start_latitude="+lat1+"&start_longitude="+lon1+"&end_latitude="+lat2+"&end_longitude="+lon2+"&token="+uber_key
			headers = {
				'Authorization': 'Token %s' % uber_key,
        'Content-Type': 'application/json'
			}
			r = requests.get(url, headers=headers)
			relationship = Relationship(nodes[i], "Travel", nodes[j], duration=(r.json())["prices"][0]["duration"], cost=(r.json())["prices"][0]["low_estimate"])
			graph.create(relationship)
		print("Finished node: " + str(i))
	return "Success"

@app.route("/api/demo", methods=["POST"])
def demo():
	location = request.json['location']
	hours = int(request.json['hours'])
	budget = str(request.json['budget'])
	seconds = str(hours * 3600)
	paths = []
	prevs = []
	query = 'START n = node(*) WHERE n.name = "'+location+'" MATCH p=n-[r:Travel*2..6]-n WHERE ALL(q in nodes(p) WHERE 1>=length(filter(m in nodes(p) WHERE m<>n AND m=q))) AND 2=length(filter(m in nodes(p) WHERE m=n)) WITH REDUCE(acc=0, rel IN r | acc+rel.duration) AS totalRel, p, REDUCE(acc=0, nod in nodes(p) | acc+nod.duration) AS totalNod, REDUCE(acc=0, rel IN r | acc+rel.cost) AS totalCost WITH p, totalCost, totalNod + totalRel AS totalDuration WHERE totalDuration < '+seconds+' AND totalCost < '+budget+' RETURN p, totalDuration, totalCost ORDER BY totalDuration DESC LIMIT 20'
	print query
	for record in graph.cypher.execute(query):
		nodes = []
		prev = ""
		for i in range(len(record.p)):
			first = record.p[i].start_node
			second = record.p[i].end_node
			if prev == "" and first["name"] == location:
				current = first
				prev = second["name"]
			elif prev == "" and second["name"] == location:
				current = second
				prev = first["name"]
			else:
				if first["name"] == prev:
					current = first
					prev = second["name"]
				else:
					current = second
					prev = first["name"]
			nodes.append({'name': current["name"], 'lat': current["lat"], 'lon': current["lon"], 'url': current['url'], 'image_url': current['image_url']})
		if sorted(nodes) not in prevs:
			prevs.append(sorted(nodes))
			paths.append({'nodes': nodes, 'duration': record.totalDuration, 'cost': record.totalCost})
			if len(paths) == 5:
				break
	return json.dumps(paths[:5])

if __name__ == "__main__":
	app.run(debug=True)
