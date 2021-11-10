from itertools import combinations

import numpy as np
import sympy as sp
import sympy.physics.quantum as spq
import hypernetx as hnx
from hnxwidget import HypernetxWidget

# global variables
guid = 0

def getUID(prefix="id#"):
    global guid

    guid = guid + 1
    return prefix + str(guid - 1)

class QuditSystem:
    def __init__(self, nb_qudits, dim, symbolic= False):
        global guid

        self.dim = dim
        self.nb_qudits = nb_qudits

        #init qudits
        self.qudits = []

        for qudit in range(nb_qudits):
            if (symbolic):
                j = 0
                state = 0
                while j < dim:
                    coeff = sp.symbols('coeff_'+str(j))
                    state += coeff*spq.Ket(j)
                    
                    j += 1
                self.qudits.append(hnx.Entity(getUID(),props={'qudit':qudit, 'state':state}))
            else:
                self.qudits.append(hnx.Entity(getUID(),props={'qudit':qudit, 'state':spq.Ket(0)}))
        
        #Initialize Hypergraph
        self.hypergraph = hnx.Hypergraph({
            getUID('system#'): self.qudits
        })
        
    def draw(self):
        hnx.draw(self.hypergraph)

    def drawBloch(self,qudit):
        pass

    # subsystems is the list of qudits to consider
    def drawStatevector(self,subsystems):
        pass

    # subsystems is the list of qudits to consider
    def drawProbabilities(self,subsystems):
        pass

    def getQuditNodes(self,qudit):
        node_list = []
        for e in self.qudits:
            if (e.props['qudit'] == qudit):
                node_list.append(e.uid)
        
        return node_list

    # subsystems = list of qudits
    def postSelect(self,qudit,state):
        node_list = []
        # Step 1: match (full or lcomb) all the nodes from qudit <qudit> with state <state>
        for e in self.qudits:
            if (e.props['qudit'] == qudit and e.props['state'] == spq.Ket(0)):
                node_list.append(e.uid)
        
        print(node_list)
        self.hypergraph = self.hypergraph.remove_nodes(node_list)

        # Step 2: generate a copy of the hypergraph permatch and update 
        # it by droppping the rest of the qudit nodes

        # Step 3: recombine the hypergraphs
