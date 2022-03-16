"""main file to run the dblp crawler
   XML API is specified under https://dblp.uni-trier.de/xml/docu/dblpxmlreq.pdf
"""
# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import re
import requests
from xml.dom import minidom
from collections import defaultdict
import argparse
import json

from bs4 import BeautifulSoup
from tqdm.auto import tqdm


def get_urlpt(name):
    """helper function to obtain the essential part of the name to URL mapping (urlpt)
       :params author_name: string of the authors name
       :returns: urlpt mapping
    """
    url = "http://dblp.uni-trier.de/search/author?xauthor=" + name
    response = requests.get(url)

    xmldoc = minidom.parseString(response.content)
    assert xmldoc.getElementsByTagName("author"), f"No author with the name '{name}' found.."

    item = xmldoc.getElementsByTagName("author")[0]

    if item.hasAttribute("urlpt"):
        return item.attributes["urlpt"].value

    return None


def get_list_of_papers(author_name: str) -> list:
    """fetches the response and parses it as xml
       :param author_name: string of the authors name
       :return: list of the publications for the given author name
    """
    # obtain the urlpt mapping. If not found, return none
    name = get_urlpt(author_name)
    if name is None:
        return None

    # uses the urlpt mapping to get the authors publication url
    url = "http://dblp.uni-trier.de/pers/xk/" + name + ".xml"
    response = requests.get(url)

    # parse the publication xml data and search for the dblpkey
    # the dblpkey are the keys of the bibliographic records
    xmldoc = minidom.parseString(response.content)
    itemlist = xmldoc.getElementsByTagName("dblpkey")

    papers = list()

    for item in itemlist:
        if item.hasAttribute("type"):
            if item.attributes["type"].value == "person record":
                continue
        rc = []
        for node in item.childNodes:
            if node.nodeType == node.TEXT_NODE:
                rc.append(node.data)
        papers.append("".join(rc))

    return papers


def get_paper_info(paper: str) -> defaultdict:
    """helper function to obtain the information of a specific paper
       :param paper: string of the paper suburl
       :return: defaultdict of the information gathered for the chosen paper
    """
    url = "http://dblp.uni-trier.de/rec/xml/" + paper + ".xml"
    response = requests.get(url)
    xmldoc = minidom.parseString(response.content)
    publication_type = paper.split("/")[0]

    paper_info = defaultdict(lambda: [])

    if publication_type == "journals":
        article_items = xmldoc.getElementsByTagName("article")
        if len(article_items) > 0:
            for item in article_items:
                for author in item.getElementsByTagName("author"):
                    paper_info["author"].append(author.firstChild.data)

                if item.getElementsByTagName("title"):
                    paper_info["title"] = item.getElementsByTagName("title")[0].firstChild.data

                paper_info["year"] = "0"
                if item.getElementsByTagName("year"):
                    paper_info["year"] = item.getElementsByTagName("year")[0].firstChild.data

                paper_info["links"] = ""
                if item.getElementsByTagName("ee"):
                    paper_info["links"] = item.getElementsByTagName("ee")[0].firstChild.data
                    pdf_links = list()
                    try:
                        html = requests.get(paper_info["links"])
                        soup = BeautifulSoup(html.text, features="html.parser")
                        for link in soup.find_all("a"):
                            # special treatment for arxiv links
                            if paper_info["links"].startswith("https://arxiv.org"):
                                link["href"] = paper_info["links"].replace("abs", "pdf", 1) + ".pdf"
                                pdf_links.append(link["href"])
                                break

                            if link["href"].lower().endswith(".pdf"):
                                # escape parsing failures für slash characters
                                link["href"] = link["href"].replace("%2", "/", 1)
                                # obtain the domain name
                                domain_string = re.search(r"^(?:[^\/]*\/){2}([^\/]*)",
                                                          html.url)
                                # if the link does not start with the domain name, concat it
                                if not link["href"].startswith(domain_string.group()):
                                    # and if it starts with another domain, use that instead
                                    if link["href"].startswith("http") or \
                                        link["href"].startswith("https"):
                                        pdf_links.append(link["href"])
                                    else:
                                        pdf_links.append(domain_string.group() + link["href"])
                                else:
                                    pdf_links.append(link["href"])
                        paper_info["pdf_links"] = pdf_links

                    except Exception as e:
                        paper_info["pdf_links"] = ""
        return paper_info

    elif publication_type == "conf":
        article_items = xmldoc.getElementsByTagName("inproceedings")
        if len(article_items) > 0:
            for item in article_items:
                for author in item.getElementsByTagName("author"):
                    paper_info["author"].append(author.firstChild.data)

                if item.getElementsByTagName("title"):
                    paper_info["title"] = item.getElementsByTagName("title")[0].firstChild.data

                paper_info["year"] = "0"
                if item.getElementsByTagName("year"):
                    paper_info["year"] = item.getElementsByTagName("year")[0].firstChild.data

                paper_info["links"] = ""
                if item.getElementsByTagName("ee"):
                    paper_info["links"] = item.getElementsByTagName("ee")[0].firstChild.data
                    pdf_links = list()
                    try:
                        html = requests.get(paper_info["links"])
                        soup = BeautifulSoup(html.text, features="html.parser")
                        for link in soup.find_all("a"):
                            # special treatment for arxiv links
                            if paper_info["links"].startswith("https://arxiv.org"):
                                link["href"] = paper_info["links"].replace("abs", "pdf", 1) + ".pdf"
                                pdf_links.append(link["href"])
                                break

                            if link["href"].lower().endswith(".pdf"):
                                # escape parsing failures für slash characters
                                link["href"] = link["href"].replace("%2", "/", 1)
                                # obtain the domain name
                                domain_string = re.search(r"^(?:[^\/]*\/){2}([^\/]*)",
                                                          html.url)
                                # if the link does not start with the domain name, concat it
                                if not link["href"].startswith(domain_string.group()):
                                    # and if it starts with another domain, use that instead
                                    if link["href"].startswith("http") or \
                                        link["href"].startswith("https"):
                                        pdf_links.append(link["href"])
                                    else:
                                        pdf_links.append(domain_string.group() + link["href"])
                                else:
                                    pdf_links.append(link["href"])
                        paper_info["pdf_links"] = pdf_links

                    except Exception as e:
                        paper_info["pdf_links"] = ""
        return paper_info
    else:
        return None


def save_to_json(name: str, data: dict) -> None:
    """helper function to dump the paper data for every author into a JSON"""
    name = name.replace(" ", "_").lower()
    output_file = open(name+".json", "w")
    json.dump(data, output_file, indent=6)
    output_file.close()


def main(author: str) -> None:
    """main function of the crawler"""

    for person in tqdm(author, desc="Crawling authors"):
        # obtain the complete list of publications for a given author
        paper_list = get_list_of_papers(person)

        if paper_list is not None:
            # dictionary of all papers with their metadata
            paper_info_list = list()
            for paper in paper_list:
                paper_info_list.append(get_paper_info(paper))
                save_to_json(person, paper_info_list)
        else:
            print(f"No papers found for '{person}' ...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--author", "-a", help="Authors to crawl", type=str, nargs="+", required=True)
    args = parser.parse_args()

    main(**vars(args))
