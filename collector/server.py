#!/usr/bin/env python3

import socket
import multiprocessing as mp
import queue
import signal
import sys
import os
import time

import parser

class ShutDownServer(Exception):
	pass

class SendMetadata(Exception):
	pass

class ServerState:
	def __init__(self):
		self.clear()
	
	def clear(self):
		self.flows = dict()
		self.switches = dict()
		self.paths = dict()
	
	def update_flow(self, flow, bytes, packets, minLatency, maxLatency, totalLatency):
		if flow in self.flows:
			self.flows[flow][0] += bytes
			self.flows[flow][1] += packets

			if self.flows[flow][2] > minLatency:
				self.flows[flow][2] = minLatency
			
			if self.flows[flow][3] < maxLatency:
				self.flows[flow][3] = maxLatency
			
			self.flows[flow][4] += totalLatency
		else:
			self.flows[flow] = [bytes, packets, totalLatency, totalLatency, totalLatency] # pkts, bytes, min/max/total latency
	
	def add(self, additional):
		# update flows
		for k, v in additional.flows.items():
			self.update_flow(k, v[0], v[1], v[2], v[3], v[4])

state = ServerState()

def stopServer(signum, frame):
	if signum == signal.SIGINT:
		raise SendMetadata
	if signum == signal.SIGTERM:
		raise ShutDownServer

def init_server():
	os.setpgid(0, 0)
	signal.signal(signal.SIGINT, stopServer)
	signal.signal(signal.SIGTERM, stopServer)

def server(result):
	global state

	init_server()

	UDP_port = 9500
	UDP_IP = '0.0.0.0'

	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
	sock.bind((UDP_IP, UDP_port))

	result.put_nowait((os.getpid(), True))

	try:
		while True:
			try:
				data, addr = sock.recvfrom(1500)
				#print('received {} bytes from {}'.format(len(data), addr))
			
				# decode packet
				hops_metadata, transport_protocol, srcIP, dstIP, srcPort, dstPort, packet_totalLen = parser.parse_int_report(data)

				if len(hops_metadata) == 0:
					continue

				flow = "{} {} {} {} {}".format(transport_protocol, srcIP, srcPort, dstIP, dstPort)

				#print("flow: {}:".format(flow))
				#print(" bytes: {}".format(packet_totalLen))
				#for i in hops_metadata:
				#	print(" {}".format(i))
				totalLatency = 0
				for i in hops_metadata:
					totalLatency += i["latency"]
				state.update_flow(flow, packet_totalLen, 1, totalLatency, totalLatency, totalLatency)
			
			except SendMetadata:
				# one packet may be incompletly added, so the more packets, the error is smaller
				# dictionaries must be copied to be sure that they are correctly serialized, because
				# serialization is performed by concurent thread
				# see https://stackoverflow.com/questions/28593103 
				tmp = ServerState()
				tmp.flows = state.flows.copy()
				result.put_nowait(tmp)
				state.clear()

			except parser.ParserError as e:
				pass
				#print("Received invalid packet: {}".format(e))

	except ShutDownServer:
		pass

	finally:
		sock.close()

def stopManager(signum, frame):
	if signum == signal.SIGINT:
		raise KeyboardInterrupt
	if signum == signal.SIGTERM:
		raise KeyboardInterrupt

if __name__ == '__main__':
	signal.signal(signal.SIGINT, stopManager)
	signal.signal(signal.SIGTERM, stopManager)

	max_processes = 2 #len(os.sched_getaffinity(0))
	processes = list()
	results = list()
	
	for i in range(max_processes):
		queue = mp.Queue()
		p = mp.Process(target=server, args=(queue,))
		p.start()
		processes.append(p)
		results.append(queue)
	
	for q, p in zip(results, processes):
		try:
			start = q.get(timeout=5)
			print("Worker {} started...".format(start[0]))
		except mp.queues.Empty:
			print("Worker {} not started in the given time".format(p.pid))
			# TODO: remove process and queue from list

	print("Startup completed")
	
	try:
		while True:
			# wait a while
			time.sleep(1)

			for v in processes:
				os.kill(v.pid, signal.SIGINT)
			
			final_result = ServerState()
			for v in results:
				c = v.get()
				final_result.add(c)
			
			# TODO: send final_result to the InfluxDB
		
	except KeyboardInterrupt:
		pass

	print("Shutting down...")

	# cleanup child process
	for v in processes:
		os.kill(v.pid, signal.SIGTERM)

	for v in processes:
		v.join()
