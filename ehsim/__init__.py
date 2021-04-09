from itertools import combinations
import json

import numpy as np

# global variables
node_nb = 0

zero_ket = np.array([1, 0], dtype=np.complex_)
one_ket = np.array([0, 1], dtype=np.complex_)
plus_ket = np.array([1 / np.sqrt(2), 1 / np.sqrt(2)], dtype=np.complex_)
minus_ket = np.array([1 / np.sqrt(2), -1 / np.sqrt(2)], dtype=np.complex_)

def getUID(prefix="id"):
    global node_nb

    node_nb = node_nb + 1
    return prefix + "_" + str(node_nb - 1)

def P2R(radii, angles):
    return radii * np.exp(1j * angles)


def R2P(x):
    return np.abs(x), np.angle(x)

class Node:
    def __init__(self, qubit, state):
        self.uid = getUID("node")
        self.qubit = qubit
        self.state = state
        self.measured = False
        self.edge_uid = None
        self.replaced = False

class Hyperedge:
    def __init__(self, amplitude, uid=None):
        self.node_uids = []
        if uid is None:
            self.uid = getUID("edge")
        else:
            self.uid = uid
        self.amplitude = amplitude


class Hypergraph:

    # TODO add support for register level operation in a later version
    def __init__(self, nb_qubits, sv=[]):
        self.nodes = {}
        self.edges = {}
        self.qubitLabels = []

        if len(sv) > 0:
            for i in range(0, len(sv)):
                prob = sv[i].real ** 2 + sv[i].imag ** 2
                if prob:

                    e = Hyperedge(sv[i])
                    self.edges[e.uid] = e

                    # create nodes
                    bits = [(i >> bit) & 1 for bit in range(nb_qubits - 1, -1, -1)]
                    j = 0
                    for bit in bits:
                        self.qubitLabels.append("q" + str(j))

                        p = Node(
                            "q" + str(j), (one_ket if bit == 1 else zero_ket)
                        )
                        # add nodes to hgraph
                        self.nodes[p.uid] = p
                        # add nodes to edge
                        self.addNodeToEdge(p.uid, e.uid)
                        j = j + 1
        else:
            for i in range(0, nb_qubits):
                self.qubitLabels.append("q" + str(i))

                node = Node("q" + str(i), np.array([1, 0], dtype=np.complex_))
                self.nodes[node.uid] = node

    def normalize_complex_arr(self, a):
        norm = np.linalg.norm(a)
        return a / norm

    def getQubitNodeIds(self, qubit):
        uids = []
        for n in self.nodes:
            if self.nodes[n].qubit == qubit:
                uids.append(self.nodes[n].uid)

        return uids

    def getQubitNodeIdInEdge(self, qubit, edge_uid):
        for n in self.nodes:
            if self.nodes[n].qubit == qubit:
                if (self.nodes[n].edge_uid is None and edge_uid is None) or (
                    self.nodes[n].edge_uid == edge_uid
                ):
                    return self.nodes[n].uid

        return None

    def getQubitNodeId(self, qubit, edge):
        uids = []
        for n in self.edges[edge].node_uids:
            if self.nodes[n].qubit == qubit:
                return self.nodes[n].uid

        return None

    def getQubitEdgeIds(self, qubit):
        uids = []
        for e in self.edges:
            node_uids = self.edges[e].node_uids
            for node_uid in node_uids:
                if self.nodes[node_uid].qubit == qubit:
                    uids.append(e)

        return uids

    def addNodeToEdge(self, node_uid, edge_uid):
        # assume edge and node exist
        if self.nodes[node_uid].edge_uid == None:
            self.nodes[node_uid].edge_uid = edge_uid
            self.edges[edge_uid].node_uids.append(node_uid)

    def deleteNode(self, node_uid):
        # assuming nodes only belong to one element
        if node_uid in self.nodes.keys():
            e_uid = self.nodes[node_uid].edge_uid

            self.nodes.pop(node_uid)

            if e_uid in self.edges.keys():
                i = self.edges[e_uid].node_uids.index(node_uid)
                self.edges[e_uid].node_uids.pop(i)

    def deleteEdge(self, edge_uid):
        for nid in self.edges[edge_uid].node_uids:
            self.nodes.pop(nid)

        self.edges.pop(edge_uid)

    # We must conbine them in distributabliy
    def combineEdges(self, a_edge_ids, b_edge_ids):
        for a_id in a_edge_ids:
            for b_id in b_edge_ids:
                a_edge = self.edges[a_id]
                b_edge = self.edges[b_id]

                e = Hyperedge(a_edge.amplitude * b_edge.amplitude)
                self.edges[e.uid] = e

                # recrerate the nodes of a inside the new edge
                for n_id in a_edge.node_uids:
                    p = Node(self.nodes[n_id].qubit, self.nodes[n_id].state)
                    p.measured = self.nodes[n_id].measured
                    self.nodes[p.uid] = p
                    self.addNodeToEdge(p.uid, e.uid)

                # recrerate the nodes of b inside the new edge
                for n_id in b_edge.node_uids:
                    p = Node(self.nodes[n_id].qubit, self.nodes[n_id].state)
                    p.measured = self.nodes[n_id].measured
                    self.nodes[p.uid] = p
                    self.addNodeToEdge(p.uid, e.uid)

        # Cleanup and delete the old nodes and edges
        for e_id in a_edge_ids:
            edge = self.edges[e_id]
            for n_id in edge.node_uids:
                self.deleteNode(n_id)

            self.deleteEdge(e_id)

        for e_id in b_edge_ids:
            edge = self.edges[e_id]
            for n_id in edge.node_uids:
                self.deleteNode(n_id)

            self.deleteEdge(e_id)

    def getGlobalPhase(self, state):
        for s in state:
            (val, angle) = R2P(s)

            # TODO is this a good convention?
            if val != 0:
                return angle

        return None

    def addGlobalPhase(self, state, angle):
        st = state.copy()

        for i, s in enumerate(st):
            (absi, angi) = R2P(s)
            st[i] = P2R(absi, angi + angle)

        return st

    def correctPhase(self, state):
        st = state.copy()

        angle = self.getGlobalPhase(st)

        for i, s in enumerate(st):
            (absi, angi) = R2P(s)
            st[i] = P2R(absi, angi - angle)

        return st

    def stateEq(self, state1, state2):
        # Correct for global phase
        st1 = self.correctPhase(state1.copy())
        st2 = self.correctPhase(state2.copy())

        for i, state in enumerate(st1):
            st1[i] = np.around(state, decimals=3)

        for i, state in enumerate(st2):
            st2[i] = np.around(state, decimals=3)

        return np.array_equal(st1, st2)

    # Transforms the full system
    def toStateVector(self, correctPhase=False):
        sv = np.array([])

        # First we deal with edges and entangled qubits
        for edge in self.edges:
            parent_amplitude = self.edges[edge].amplitude
            tmp_sv = np.array([])

            for node_uid in self.edges[edge].node_uids:
                if len(tmp_sv) == 0:
                    tmp_sv = np.around(self.nodes[node_uid].state, 3)
                else:
                    tmp_sv = np.kron(np.around(self.nodes[node_uid].state, 3), tmp_sv)

            tmp_sv = parent_amplitude * tmp_sv

            if len(sv) == 0:
                sv = tmp_sv
            else:
                sv = sv + tmp_sv

        # Then we deal with the non-entangled ones
        # Kroenecker product of all nodes
        for node_uid in self.nodes:
            if self.nodes[node_uid].edge_uid is None:
                if len(sv) == 0:
                    sv = np.around(self.nodes[node_uid].state, 3)
                else:
                    sv = np.kron(np.around(self.nodes[node_uid].state, 3), sv)

        if correctPhase:
            sv = self.correctPhase(sv)

        for i, el in enumerate(sv):
            sv[i] = np.around(sv[i], 3)

        return sv

    # m Hyperedge matrix
    # runs one merge
    # m isdict with edges and qubits
    # a is dictionary with edge amplitudes

    def factorRec(self, m, amps, measured_qubits=[], steps=None):
        if steps is not None and steps == 0:
            # Stop!
            return (m, amps)

        if len(m.keys()) == 1:
            return (m, amps)

        if steps is not None and steps > 0:
            steps = steps - 1

        res = {}
        processed = []
        # do one run
        for e1 in m:
            processed.append(e1)
            for e2 in m:
                if e2 not in processed:
                    # can we merge e1 and e2
                    nb_diff = 0
                    a = None
                    b = None
                    e = None
                    x = amps[e1]
                    y = amps[e2]
                    nodes = {}

                    # First we need to get the cummulative global phase and correct locally
                    ph1 = 0
                    for n in m[e1]:
                        ph1 = ph1 + self.getGlobalPhase(m[e1][n])

                    ph2 = 0
                    for n in m[e2]:
                        ph2 = ph2 + self.getGlobalPhase(m[e2][n])

                    # We now try to merge the edges
                    diff_but_measured = 0
                    for n in m[e1]:

                        if not self.stateEq(m[e1][n], m[e2][n]):
                            nb_diff += 1
                            if n in measured_qubits:
                                diff_but_measured += 1

                            # we add the collected global phases to each before addition
                            st1 = self.addGlobalPhase(m[e1][n], ph1)
                            st2 = self.addGlobalPhase(m[e2][n], ph2)

                            nodes[n] = self.normalize_complex_arr(
                                (amps[e1] * st1) + (amps[e2] * st2)
                            )
                            a = np.reshape(st1, (len(st1), 1))
                            b = np.reshape(st2, (len(st2), 1))
                            e = np.reshape(nodes[n], (len(nodes[n]), 1))
                        else:
                            # we must take the state without global phase as we assumed we've corrected it accordingly
                            # if merging is not successful the global phases shouldn't be altered
                            nodes[n] = self.correctPhase(m[e1][n])

                    # We process the merge really only if the edges we compared has 0 or 1 difference and they do not contain measured qubits
                    if nb_diff <= 1 and diff_but_measured == 0:
                        res[e1 + "_" + e2] = nodes

                        te = np.transpose(e)
                        amps[e1 + "_" + e2] = np.dot(te, (x * a + y * b))[0]

                        for e3 in m:
                            if e3 != e1 and e3 != e2:
                                res[e3] = m[e3]

                        # recursive step
                        return self.factorRec(res, amps, measured_qubits, steps)

        # If we end up here it means we havent simplified anything
        return (m, amps)

    # m Hyperedge dict
    def deleteEdges(self, m):
        for e in m:
            for q in m[e]:
                self.deleteNode(self.getQubitNodeId(q, e))

            self.deleteEdge(e)

    # m Hyperedge dict
    def createEdges(self, m, amps, measured_qubits):
        if len(m.keys()) <= 1:
            for e in m:
                for q in m[e]:
                    node = Node(q, m[e][q])
                    if q in measured_qubits:
                        node.measured = True

                    self.nodes[node.uid] = node
        else:
            t = {}
            for e in m:
                for q in m[e]:
                    if q not in t.keys():
                        t[q] = {}

                    t[q][e] = m[e][q]

            # Check which qubits are entangled
            non_entangled = []

            # There is a big edge case here where
            # one might still need to do a phase correction, etc.
            # TODO
            """for q in t:
                q_first = None
                all_equal = True
                for e in t[q]:
                    if (q_first is None):
                        q_first = t[q][e]
                    else:
                        all_equal = all_equal and (self.stateEq(t[q][e],q_first))

                if (all_equal):
                    non_entangled.append(q)"""

            populated_qubits = []
            for e in m:
                edge = Hyperedge(amps[e], e)
                self.edges[edge.uid] = edge
                for q in m[edge.uid]:
                    if q not in populated_qubits or q not in non_entangled:
                        node = Node(q, m[edge.uid][q])
                        if q in measured_qubits:
                            node.measured = True

                        self.nodes[node.uid] = node
                        populated_qubits.append(q)

                        if q not in non_entangled:
                            self.addNodeToEdge(node.uid, edge.uid)

    # Move all node global phases are bubbled up to the corresponding edges!
    def factorPhases(self, qubits):
        for node_uid in self.nodes:
            edge_uid = self.nodes[node_uid].edge_uid
            if edge_uid is not None:
                angle_n = self.getGlobalPhase(self.nodes[node_uid].state)
                self.nodes[node_uid].state = self.correctPhase(
                    self.nodes[node_uid].state
                )

                (val_e, angle_e) = R2P(self.edges[edge_uid].amplitude)
                self.edges[edge_uid].amplitude = P2R(val_e, angle_e + angle_n)

    def splitEdgeZ(self, edge_uid, qubit):
        node = self.nodes[self.getQubitNodeIdInEdge(qubit, edge_uid)]

        if (not self.stateEq(node.state,zero_ket) and not self.stateEq(node.state,one_ket)):
            if edge_uid is None:
                # TODO This is a bit dirty ;)
                # create an edge for the 1 component
                edge = Hyperedge(one_ket[1])
                self.edges[edge.uid] = edge

                # populate initial edge
                for n_id in self.nodes:
                    self.addNodeToEdge(n_id, edge.uid)
            else:
                edge = self.edges[edge_uid]

            # Create Edge for the 0 component
            e = Hyperedge(edge.amplitude * node.state[0])
            self.edges[e.uid] = e

            # recrerate the nodes of a inside the new edge
            for n_id in edge.node_uids:
                state = self.nodes[n_id].state
                if n_id == node.uid:
                    state = zero_ket

                p = Node(self.nodes[n_id].qubit, state)
                p.measured = self.nodes[n_id].measured
                self.nodes[p.uid] = p
                self.addNodeToEdge(p.uid, e.uid)

            # Update current edge to reflect the 1 component
            edge.amplitude = edge.amplitude * node.state[1]
            for n_id in edge.node_uids:
                if n_id == node.uid:
                    self.nodes[n_id].state = one_ket

    # TODO Measure a set of qubits
    # TODO Revise preconditions for the op methods
    # TODO Update th rest of the codebase to account for non measured nodes
    # TODO probably don't allow for any gates on non measured nodes (maybe bitflips?)
    # TODO we lose the measurement labels when factoring
    def measure(self, qubits):
        # iterate over each hyper edge the qubit is in
        for q in qubits:
            edge_ids = self.getQubitEdgeIds(q)
            if len(edge_ids) == 0:
                # if the qubit is in the comp. basis then we just flag it as measured = True
                # remve any global phase
                # Note: Quirk keeps track of the phase so that a statevector (assuming measurement deferred can still be shown)
                # self.nodes[node.uid].state = self.correctPhase(node.state)
                node = self.nodes[self.getQubitNodeIdInEdge(q, None)]
                self.nodes[node.uid].measured = True
                if not self.stateEq(node.state, one_ket) and not self.stateEq(
                    node.state, zero_ket
                ):
                    # if the qubit is not then we need to split the edge into 2.
                    # One where the node will be in the 0 state + measured = True
                    # One where the node will be in the 1 state + measured = True
                    self.splitEdgeZ(None, node.qubit)
            else:
                for e_id in edge_ids:
                    # if the qubit is in the comp. basis then we just flag it as measured = False
                    # remve any global phase
                    # Note: Quirk keeps track of the phase so that a statevector (assuming measurement deferred can still be shown)
                    # self.nodes[node.uid].state = self.correctPhase(node.state)
                    node = self.nodes[self.getQubitNodeIdInEdge(q, e_id)]
                    self.nodes[node.uid].measured = True
                    if not self.stateEq(node.state, one_ket) and not self.stateEq(
                        node.state, zero_ket
                    ):
                        # if the qubit is not then we need to split the edge into 2.
                        # One where the node will be in the 0 state + measured = True
                        # One where the node will be in the 1 state + measured = True
                        self.splitEdgeZ(e_id, node.qubit)

        return

    def normalizeEdgeAmplitudes(self):
        ampl = []
        for euid in self.edges:
            ampl.append(self.edges[euid].amplitude)

        ampl = self.normalize_complex_arr(ampl)

        for index, euid in enumerate(self.edges):
            self.edges[euid].amplitude = ampl[index]

    # TODO calculate how much we are omitting (like Quirk does)
    def postSelectZ(self, qubits, state=zero_ket):
        self.measure(qubits)
        loss = 0
        for qubit in qubits:
            nodeIds = self.getQubitNodeIds(qubit)
            for nodeId in nodeIds:
                node = self.nodes[nodeId]
                if not self.stateEq(node.state, state):
                    if node.edge_uid is not None:
                        edge = self.edges[node.edge_uid]
                        loss = loss + (
                            edge.amplitude.real ** 2 + edge.amplitude.imag ** 2
                        )

                    self.deleteEdge(node.edge_uid)

        self.normalizeEdgeAmplitudes()
        return loss

    def expandQubits(self, a, b):
        #if one of the qubits is not entangled but the other is we need to add the qubit to all corresponding edges before we start with the operation (sort of decompress)
        #preprocessing NOT tested
        a_edge_ids = self.getQubitEdgeIds(a)
        b_edge_ids = self.getQubitEdgeIds(b)
        
        if (len(a_edge_ids) == 0 and len(b_edge_ids) != 0):
            a_node_ids = self.getQubitNodeIds(a)
            a_node = self.nodes[a_node_ids[0]]
            for edge_id in b_edge_ids:
                #create node
                p = Node(a_node.qubit,a_node.state)
                #add nodes to hgraph
                self.nodes[p.uid] = p
                #add nodes to edge
                self.addNodeToEdge(p.uid,edge_id)
            
            #delete original node
            #did nt belong t any edge anyway
            self.deleteNode(a_node.uid)
        
        elif (len(b_edge_ids) == 0 and len(a_edge_ids) != 0):
            b_node_ids = self.getQubitNodeIds(b)
            b_node = self.nodes[b_node_ids[0]]
            for edge_id in a_edge_ids:
                #create node
                p = Node(b_node.qubit,b_node.state)
                #add nodes to hgraph
                self.nodes[p.uid] = p
                #add nodes to edge
                self.addNodeToEdge(p.uid,edge_id)
            
            #delete original node
            #did nt belong t any edge anyway
            self.deleteNode(b_node.uid)
        
        #if both entangled but in different edges we need to do some preprocessing as well
        shared_edges = list(set(a) & set(b))

        #tbh, if edges are not shared they, the intersection must be empty. Any other set-up it's just not a valid state
        if (len(shared_edges) == 0):
            self.combineEdges(a_edge_ids,b_edge_ids)

        #SPLIT a
        a_edge_ids = self.getQubitEdgeIds(a)
        if (len(a_edge_ids) != 0):
            for eid in a_edge_ids:
                self.splitEdgeZ(eid,a)
        else:
            self.splitEdgeZ(None,a)

        #SPLIT b
        b_edge_ids = self.getQubitEdgeIds(b)
        if (len(b_edge_ids) != 0):
            for eid in b_edge_ids:
                self.splitEdgeZ(eid,b)
        else:
            self.splitEdgeZ(None,b)

        

    # Factor a specific set of entangled qubits
    # TODO add a verbose mode that explains a bit more what's going on (what's being merged)
    def factorQubits(self, qubits, steps=None, verbose=False):
        # preprocessing: Make sure all node global phases are bubbled up to the crresponding edges!
        self.factorPhases(qubits)

        # build matrix and check if exactly all the qubits are in hyperedges
        m = {}
        amps = {}
        error = False
        measured_qubits = []
        for q in qubits:
            edge_ids = self.getQubitEdgeIds(q)
            if len(edge_ids) == 0:
                error = "qubit " + q + " is not entangled"
            for e in edge_ids:
                if e not in m.keys() and qubits.index(q) == 0:
                    m[e] = {}
                    amps[e] = self.edges[e].amplitude
                elif e not in m.keys():
                    error = "The qubits are not entangled all together"

                for n in self.edges[e].node_uids:
                    if self.nodes[n].qubit not in qubits:
                        error = "The qubits are entangled with others not specified in the input"
                    if self.nodes[n].qubit == q:
                        m[e][q] = self.nodes[n].state
                        if (
                            self.nodes[n].measured
                            and self.nodes[n].qubit not in measured_qubits
                        ):
                            measured_qubits.append(self.nodes[n].qubit)

        if error:
            print(error)
            return

        # call recursive part
        (m_simp, amps_simp) = self.factorRec(m, amps, measured_qubits, steps)

        # process output dict
        self.deleteEdges(m)
        self.createEdges(m_simp, amps_simp, measured_qubits)

    def simplifiedState(self, state):
        if (self.stateEq(state,zero_ket)):
            return "|0>"

        if (self.stateEq(state,one_ket)):
            return "|1>"

        if (self.stateEq(state,plus_ket)):
            return "|+>"

        if (self.stateEq(state,minus_ket)):
            return "|->"
        
        return str(state)

    def print_raw(self):
        print("      ".join(str(ql) for ql in self.qubitLabels))
        print("------".join("--" for ql in self.qubitLabels))  
        phelper = []
        
        for e in self.edges:
            phelper = []
            for ql in self.qubitLabels:
                nid = self.getQubitNodeIdInEdge(ql,e)

                if (nid is not None):
                    replaced = ' '
                    if (self.nodes[nid].replaced):
                        replaced = '*'

                    phelper.append(self.simplifiedState(self.nodes[nid].state)+replaced)
                else:
                    phelper.append("N/A")
            
            if (len(phelper) != 0):
                phelper.append("Amplitude:"+str(self.edges[e].amplitude))

            print("     ".join(str(x) for x in phelper))
        
        phelper = []
        for ql in self.qubitLabels:
            nid = self.getQubitNodeIdInEdge(ql,None)
            systemEmpty = True

            if (nid is not None):
                systemEmpty = False
                replaced = ' '
                if (self.nodes[nid].replaced):
                    replaced = '*'

                phelper.append(self.simplifiedState(self.nodes[nid].state)+replaced)
            else:
                phelper.append("N/A")

        if (not systemEmpty):
            if (len(phelper) != 0):
                    phelper.append("Not Entangled")

            print("     ".join(str(x) for x in phelper))
        
        print("      ".join("  " for ql in self.qubitLabels))
        print(self.toStateVector())
        print("------".join("--" for ql in self.qubitLabels))
        print("      ".join("  " for ql in self.qubitLabels))
        print("      ".join("  " for ql in self.qubitLabels))
        
    #
    # match [1,1,0]
    # edge {uid = ...}
    # map ["q0","q1","q2"]
    def isMatch(self,match,edge,qubit_map):
        euid = None
        if (edge is not None):
            euid = self.edges[edge].uid

        for i,m in enumerate(match):
            q = qubit_map[i] #TODO check for error

            if (self.getQubitNodeIdInEdge(q,euid) is None):
                return False
            else:
                node = self.nodes[self.getQubitNodeIdInEdge(q,euid)]
                if (not self.stateEq(node.state,m)):
                    return False

        return True
    
    def replaceMatch(self,edge,replace,qubit_map):
        euid = None
        if (edge is not None):
            euid = self.edges[edge].uid

        for i,m in enumerate(replace):
            q = qubit_map[i] #TODO check for error

            if (not self.nodes[self.getQubitNodeIdInEdge(q,euid)].replaced):
                self.nodes[self.getQubitNodeIdInEdge(q,euid)].state = m
                self.nodes[self.getQubitNodeIdInEdge(q,euid)].replaced = True

    #input_map=["q0","q1","q2"]
    def rewrite(self,rules,input_map):
        #set all replacement tracking t False
        for n in self.nodes:
            self.nodes[n].replaced = False

        #Expand mapped qubits
        fq = input_map[0]
        if (len(input_map) == 1):
            nids = self.getQubitNodeIds(fq)
            for nid in nids:
                node = self.nodes[nid]
                self.splitEdgeZ(node.edge_uid,fq)
        else:
            for index, qubit in enumerate(input_map):
                if index > 0:
                    self.expandQubits(input_map[index - 1], input_map[index])

        for rule in rules:
            #find matches in edges
            # TODO if th edge has been touched previously shouldnt match anymore
            for e in self.edges:
                if (self.isMatch(rule['match'],e,input_map)):
                    self.replaceMatch(e,rule['replace'],input_map)
            
            #find matches in system
            if (self.isMatch(rule['match'],None,input_map)):
                    self.replaceMatch(None,rule['replace'],input_map)