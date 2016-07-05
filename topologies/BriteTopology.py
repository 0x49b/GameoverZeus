#!/usr/bin/env python2.7
# coding=UTF-8
"""This file defines a topology that reads a random network generated with BRITE and creates a mininet topology from it."""

import logging
import re
import requests
import time
from abc import abstractmethod, ABCMeta
from mininet.net import Mininet

from AbstractTopology import AbstractTopology
from utils.FloodlightController import FloodlightController

emptyLineRe = re.compile(r"^\s*$")  # Matches an empty line


def createGraphFromBriteFile(inputfilename, accepters):
    """Reads a BRITE output file and passes its contents to the accepters.
    :type accepters: list of BriteGraphAccepter"""
    # An example input file can be found in testfiles/flatrouter.brite

    assert isinstance(inputfilename, str)
    for accepter in accepters:
        assert isinstance(accepter, BriteGraphAccepter)

    with open(inputfilename, mode="r") as inputfile:
        _readHeader(inputfile, accepters)
        _readNodes(inputfile, accepters)
        _readEdges(inputfile, accepters)

    for acc in accepters:
        acc.writeFooter()


def _readHeader(inputfile, accepters):
    """Parses the header of a BRITE inputfile and extracts the name of the model used to generate the random topology
    and the number of nodes and edges.
    :type accepters: list of BriteGraphAccepter"""
    firstline = inputfile.readline()
    secondline = inputfile.readline()

    # Parse first line of the header
    regex = re.compile(r"Topology:\s*\(\s*(\d+)\s*Nodes,\s*(\d+)\s*Edges\s*\)")
    match = regex.match(firstline)
    assert match is not None, "First line of file %s is invalid: %s" % (inputfile.name, firstline)
    num_nodes, num_edges = match.group(1, 2)

    # Parse second line
    # Model (1 - RTWaxman):  20 100 100 1  2  0.15000000596046448 0.20000000298023224 1 1 10.0 1024.0
    regex = re.compile(r"Model\s*\(\d+\s*-\s*([\w_-]+)\).*")
    # regex = re.compile(r"Model\s*\(\d+\s*-\s*([\w_-])\):.*")
    match = regex.match(secondline)
    assert match is not None, "Second line of file %s is invalid: %s" % (inputfile.name, secondline)
    modelname = match.group(1)

    for acc in accepters:
        acc.writeHeader(int(num_nodes), int(num_edges), str(modelname))

    while True:
        line = inputfile.readline()
        if not line.startswith("Model"):
            break


def _readNodes(inputfile, accepters):
    """Parses the list of nodes
    :type accepters: list of BriteGraphAccepter"""

    # Matches one of the lines describing a single node
    nodeRe = re.compile(r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d-]+)\s([\w_-]+)\s*")

    # Skip over beginning
    while True:
        line = inputfile.readline()
        if emptyLineRe.match(line):
            continue
        elif re.compile("Nodes:.*").match(line):
            break

    # Match the actual nodes
    while True:
        line = inputfile.readline()
        match = nodeRe.match(line)
        if match:
            nodeid, asid, type = match.group(1, 6, 7)
            for acc in accepters:
                acc.addNode(int(nodeid), int(asid), str(type))
        elif emptyLineRe.match(line):
            # All nodes were parsed
            break
        else:
            logging.warning("File %s contained invalid node description: %s" % (inputfile.name, line))
            continue


def _readEdges(inputfile, accepters):
    """Parses the list Edges
    :type accepters: list of BriteGraphAccepter"""

    # Matches one of the lines describing an edge
    edgeRe = re.compile(
        r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+"
        r"(\d+\.\d+)\s+([\d-]+)\s+([\d-]+)\s+([\w_-]+)\s+([-_\w]+)\s*")

    # Skip over beginning
    while True:
        line = inputfile.readline()
        if (emptyLineRe.match(line)):
            continue
        elif (re.compile("Edges:.*").match(line)):
            break

    # Match the actual edges
    while True:
        line = inputfile.readline()
        match = edgeRe.match(line)
        if match:
            edgeid, fromNode, toNode, communicationDelay = match.group(1, 2, 3, 5)
            bandwidth, fromAS, toAS, type = match.group(6, 7, 8, 9)
            for acc in accepters:
                acc.addEdge(int(edgeid), int(fromNode), int(toNode), float(communicationDelay),
                            float(bandwidth), int(fromAS), int(toAS), str(type))
        elif emptyLineRe.match(line):
            # All nodes were parsed
            break
        else:
            logging.warning("File %s contained invalid node description: %s" % (inputfile.name, line))
            continue


class BriteGraphAccepter(object):
    """This is the base class for all objects where createGraphFromBriteFile will write its output to.
    It defines some callbacks that are invoked by createGraphFromBriteFile."""
    __metaclass__ = ABCMeta
    wroteHeader = False

    @abstractmethod
    def writeHeader(self, num_nodes, num_edges, modelname):
        """Invoked when starting to read the BRITE output file"""
        self.wroteHeader = True

    @abstractmethod
    def addNode(self, nodeid, asid, nodetype):
        """Invoked when reading a node
        :param nodeid: unique id of this node
        :param asid: unique of the AS this node belongs to
        :param nodetype: Whether this node is at the border of an AS or in the middle of one"""
        assert self.wroteHeader, "You have to invoke writeHeader() first"

    @abstractmethod
    def addEdge(self, edgeid, fromNode, toNode, communicationDelay, bandwidth, fromAS, toAS, edgetype):
        """Invoked when reading an edge.
        :param edgeid: Unique id of this edge
        :param fromNode: source of the edge
        :param toNode: target of the edge
        :param communicationDelay: How long it takes to send a packet along this edge
        :type communicationDelay: Float
        :param bandwidth: How much data can be send along this edge.
        :type bandwidth: Float
        :param fromAS: AS of the source node
        :param toAS: AS of the target node
        :param edgetype: Whether this edge is between two AS or within an AS"""
        assert self.wroteHeader, "You have to invoke writeHeader() first"

    @abstractmethod
    def writeFooter(self):
        """Invoked after all nodes and edges have been read"""
        pass


class BriteTopology(AbstractTopology, BriteGraphAccepter):
    """The mininet topology created from the given BRITE output file.
    It will have a number of interconnected autonomous systems and each AS will have one switch and a number of
    hosts. Each host in an AS is connected to that switch."""

    def __init__(self, mininet=Mininet(controller=FloodlightController), opts=dict()):
        """
        Initialises the LayeredTopology, so that layers can be added.
        :type mininet: Mininet
        """
        AbstractTopology.__init__(self, mininet)
        self.started = False
        self.autonomousSystems = dict()
        self.modelname = None
        self.opts = opts
        self.firewallRules = []

    def writeHeader(self, num_nodes, num_edges, modelname):
        """Invoked when starting to read the BRITE output file"""
        super(BriteTopology, self).writeHeader(num_nodes, num_edges, modelname)
        self.modelname = modelname

    def addNode(self, nodeid, asid, nodetype):
        """Converts a node in the BRITE output file to a mininet host. Invoked for every node in the BRITE output file."""

        super(BriteTopology, self).addNode(nodeid, asid, nodetype)
        assert not self.started

        self.mininet.addHost(_createBotname(nodeid), opts=self.opts)
        bot = self.mininet.getNodeByName(_createBotname(nodeid))

        if not self.autonomousSystems.has_key(asid):
            autsys = _AutonomousSystem()
            autsys.asid = asid
            autsys.botdict = dict()
            autsys.switch = self.mininet.addSwitch(_createSwitchname(asid))
            self.autonomousSystems[asid] = autsys

        self.autonomousSystems[asid].botdict[nodeid] = bot
        self.mininet.addLink(bot, self.autonomousSystems[asid].switch)

    def addEdge(self, edgeid, fromNode, toNode, communicationDelay, bandwidth, fromAS, toAS, edgetype):
        """Invoked for every edge in the BRITE output file. Converts that edge into a connection between two mininet hosts."""
        super(BriteTopology, self).addEdge(edgeid, fromNode, toNode, communicationDelay, bandwidth,
                                           fromAS, toAS, edgetype)
        assert not self.started

        self.firewallRules.append(_FirewallRule(fromNode, toNode))
        self.firewallRules.append(_FirewallRule(toNode, fromNode))

    def writeFooter(self):
        """Invoked after fully reading the BRITE output file"""
        super(BriteTopology, self).writeFooter()
        self._connectSwitchesToSwitches()
        self._connectASNodesToSwitches()

    def start(self):
        """Starts operation of the defined Topology. It will also start the command for each of the layers."""
        self.started = True
        self.mininet.start()
        time.sleep(5)
        self._applyFirewallRules()
        self._startFirewall()
        time.sleep(3)

    def stop(self):
        """Stops the operation of this topology. Usually called when the experiment is over."""
        self.mininet.stop()
        pass

    def _connectSwitchesToSwitches(self):
        """Connects all the switches to each other."""
        askeys = self.autonomousSystems.keys()
        for i in range(1, len(askeys)):
            switch1 = self.autonomousSystems[askeys[i - 1]].switch
            switch2 = self.autonomousSystems[askeys[i]].switch
            self.mininet.addLink(switch1, switch2)

    def _connectASNodesToSwitches(self):
        """Connects the nodes in a common autonomous system to their switch"""
        for autsys in self.autonomousSystems.values():
            for bot in autsys.botdict.values():
                self.mininet.addLink(autsys.switch, bot)

    # TODO: Move this method to the controller class/file
    def _applyFirewallRules(self):
        """Applies the firewall rules that were created while creating the topology"""
        for rule in self.firewallRules:
            response = requests.post("http://localhost:8080/wm/firewall/rules/json",
                                     data=str(rule.toJSON(self.mininet)))
            print "Added Rule: ", rule.toJSON(self.mininet), " ", response.text
            if not response.status_code == 200:
                logging.warning("Firewall rule could not be added: %s %d" % (rule, response.status_code))

    # TODO: Move this method to the controller class/file
    def _startFirewall(self):
        """Starts the firewall in the Floodlight controller."""
        response = requests.get("http://localhost:8080/wm/firewall/module/enable/json")
        if not response.status_code == 200:
            logging.warning("Firewall could not be enabled: response.status_code == %d" % response.status_code)


class _FirewallRule(object):
    """A rule for the firewall that forbids or allows communication between two hosts"""
    def __init__(self, fromHost, toHost, action="ALLOW"):
        self.fromHost = fromHost
        self.toHost = toHost
        self.action = action

    def toJSON(self, mininet):
        fromBot = mininet.getNodeByName(_createBotname(self.fromHost))
        toBot = mininet.getNodeByName(_createBotname(self.toHost))
        return '{"src-ip":"%s", "dst-ip":"%s", "action":"%s"}' % (fromBot.IP(), toBot.IP(), self.action)

class _AutonomousSystem(object):
    """A value class for an autonomous system as generated by BRITE"""
    botdict = dict()
    switch = None
    asid = None

    def __len__(self):
        return len(self.botdict.values())


def _createBotname(nodeid):
    return "bot%d" % nodeid


def _createSwitchname(asid):
    return "sw%d" % asid
