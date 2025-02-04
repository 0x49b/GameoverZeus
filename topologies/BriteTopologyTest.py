#!/usr/bin/env python2
# coding=UTF-8
import logging
import os
import time
import unittest

from timeout_decorator import timeout
from mininet.net import Mininet

from BriteTopology import BriteTopology, applyBriteFile, BriteGraphAccepter
from resources import emu_config
from utils import Floodlight

mn = Mininet(controller=Floodlight.Controller)

class BriteFileReaderTest(unittest.TestCase):
    """Tests whether a BRITE file can be parsed"""
    inputfilename = emu_config.basedir + "/testfiles/flatrouter.brite"

    def testReadToMockAccepter(self):
        accepter = MockAccepter()
        applyBriteFile(self.inputfilename, [accepter])
        self.assertEquals("RTWaxman", accepter.model_name)
        self.assertEquals(3, accepter.num_nodes)
        self.assertEquals(5, accepter.num_edges)


class MockAccepter(BriteGraphAccepter):
    """Counts the number of nodes and edges that are seen"""
    num_nodes = 0
    num_edges = 0
    model_name = None

    def writeHeader(self, num_nodes, num_edges, modelname):
        self.model_name = modelname

    def addNode(self, nodeid, asid, nodetype):
        self.num_nodes += 1

    def addEdge(self, edgeid, fromNode, toNode, communicationDelay, bandwidth, fromAS, toAS, edgetype):
        self.num_edges += 1

    def writeFooter(self):
        pass

class BriteTopologyTest(unittest.TestCase):
    """Tests whether two specific BRITE output files are parsed correctly"""

    def setUp(self):
        self.topology = BriteTopology(mininet=mn, probability_of_cpulimitation=0.8)

    @classmethod
    def tearDownClass(cls):
        os.system("mn -c")

    def testFlatRouter(self):
        applyBriteFile(emu_config.basedir + "/testfiles/flatrouter.brite", [self.topology])
        self.assertEquals(2, len(self.topology.autonomousSystems))
        self.assertEquals(2, len(self.topology.autonomousSystems[1]))
        self.assertEquals("bot1", self.topology.autonomousSystems[2].botdict[1].name)

    def testTopDown(self):
        applyBriteFile(emu_config.basedir + "/testfiles/topdown.brite", [self.topology])
        self.assertEquals(4, len(self.topology.autonomousSystems))
        self.assertEquals(5, len(self.topology.autonomousSystems[7]))
        self.assertEquals("bot157", self.topology.autonomousSystems[9].botdict[157].name)


@unittest.skip("Only one of BriteMininetFlatrouterTest and BriteMininetTopdownTest can be active at the same time."
               "Otherwise they stop working because mn.")
class BriteMininetFlatrouterTest(unittest.TestCase):
    """Tests if the topology created from the flatrouter file (with autonomous systems disabled) works in mn"""

    @classmethod
    def setUpClass(cls):
        cls.topology = BriteTopology(mininet=mn)
        applyBriteFile(emu_config.basedir + "/testfiles/flatrouter.brite", [cls.topology])
        cls.topology.start()

    @classmethod
    def tearDownClass(cls):
        cls.topology.stop()
        time.sleep(2)
        os.system("mn -c")

    @timeout(15)
    def testPingAll(self):
        """test if pingAll succeeds without packet loss"""
        packet_loss = self.topology.mininet.pingAll()
        self.assertEquals(0, packet_loss)


class BriteMininetTopdownTest(unittest.TestCase):
    """Tests if the topology created from the topdown file (with autonomous systems enabled) works in mn"""

    @classmethod
    def setUpClass(cls):
        cls.topology = BriteTopology(mn)
        applyBriteFile(emu_config.basedir + "/testfiles/topdown.brite", [cls.topology])
        cls.topology.start()

    @classmethod
    def tearDownClass(cls):
        cls.topology.stop()
        time.sleep(2)
        os.system("mn -c")

    @timeout(15)
    def testPingAll(self):
        """test if pingAll succeeds without packet loss"""
        packet_loss = self.topology.mininet.pingAll()
        self.assertEquals(0, packet_loss)

if __name__ == '__main__':
    logging.basicConfig(format="%(threadName)s: %(message)s", level=logging.DEBUG)
    unittest.main()
