#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import KA JIRA RSS export to GitHub

To use, create credentials.json: {"username": "yourusername", "password": "password"}
with your GitHub credentials. Beware API limits!
"""
from lxml import etree
import re
import time
import json
import argparse
import github
import argparse
from ansicolor import red, black

parser = argparse.ArgumentParser()
parser.add_argument("filename", help="The JIRA XML RSS export to read")
parser.add_argument("-d", "--delay", type=int, default=10, help="How long to delay between creating issue")
args = parser.parse_args()

etree = etree.parse(args.filename)

rss = etree.getroot()
channel = rss.getchildren()[0]
items = channel.xpath("item")

def itemToDict(item):
    "Extract important attributes from an item and "
    key = item.xpath("key")[0].text
    title = item.xpath("title")[0].text
    created = item.xpath("created")[0].text
    reporter = item.xpath("reporter")[0].text
    resolution = item.xpath("resolution")[0].text
    description = item.xpath("description")[0].text
    preview_url = item.xpath("customfields/customfield[@id='customfield_10027']//customfieldvalue")[0].text
    issue_type = item.xpath("customfields/customfield[@id='customfield_10300']//customfieldvalue")[0].text
    framework = item.xpath("customfields/customfield[@id='customfield_10029']//customfieldvalue")[0].text
    try:
        exercise = item.xpath("customfields/customfield[@id='customfield_10024']//customfieldvalue")[0].text
    except IndexError:
        exercise = None
    edit_url = item.xpath("customfields/customfield[@id='customfield_10028']//customfieldvalue")[0].text
    return {
        "id": key, "title": title, "created": created,
        "reporter": reporter, "resolution": resolution,
        "preview_url": preview_url, "issue_type": issue_type,
        "framework": framework, "exercise": exercise,
        "edit_url": edit_url, "description": description
    }

def formatItem(item):
    return """
Created: {0}
Reported by: {1}
Issue type: {5}
JIRA status: {2}
Links: [Preview]({3}), [Edit]({4})

{6}
    """.format(item["created"], item["reporter"], item["resolution"],
               item["preview_url"], item["edit_url"], item["issue_type"], item["description"])


def find_issue_keys(repo):
    """Generate all issue keys for correctly named GitHub issues"""
    for issue in repo.get_issues(): # iterate open issues
        # Try to search for key
        m = re.search(r"\[([A-Z]{2}-\d+)\]", issue.title)
        if m is None:
            continue  # Ignore this issue
        yield m.group(1)

def createGithubIssue(repo, item):
    "Create a GitHub issue"
    repo.create_issue(item["title"], formatItem(item))

jiraItems = [itemToDict(item) for item in items]

with open("credentials.json") as credentialsFile:
    credentials = json.load(credentialsFile)
gh = github.Github(credentials["username"], credentials["password"])

repo = gh.get_repo("ulikoehler/KADeutschIssues")
issues = repo.get_issues()

# Find issues which are in JIRA but not in GitHub
jiraKeys = set([i["id"] for i in jiraItems])
githubKeys = set(find_issue_keys(repo))
missing_items = jiraKeys.symmetric_difference(githubKeys)

print("Creating {0} new issues on GitHub...\n".format(len(missing_items)))

# Iterate every JIRA item, skip items already on github & submit new issue for remaining ones
todo = []
for item in jiraItems:
    if item["id"] in missing_items:
        todo.append(item)

# Cant use for loop because we might need to retry
idx = 0
while idx < len(todo):
    item = todo[idx]
    try:
        createGithubIssue(repo, item)
        print("Created issue #{0}: {1}".format(idx + 1, item["title"]))
        time.sleep(float(args.delay))
        idx += 1# Next item only on success
    except github.GithubException as e:
        print(red("GitHub error, likely rate limiting (retrying in 60s): {0}".format(e), bold=True))
        time.sleep(60.)
        # Retry this item
