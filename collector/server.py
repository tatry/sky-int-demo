#!/usr/bin/env python3

import socket
import multiprocessing as mp
import queue
import signal
import sys
import os
import time
import copy

import influxdb

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
			self.flows[flow] = [bytes, packets, minLatency, maxLatency, totalLatency]
	
	def update_switch(self, switch_key, switch_id, in_port, out_port, flow, bytes, packets, minLatency, maxLatency, latency):
		if switch_key in self.switches:
			self.switches[switch_key][4] += bytes
			self.switches[switch_key][5] += packets

			if self.switches[switch_key][6] > minLatency:
				self.switches[switch_key][6] = minLatency
			
			if self.self.switches[switch_key][7] < maxLatency:
				self.switches[switch_key][7] = maxLatency
			
			self.switches[switch_key][8] += latency
		else:
			self.switches[switch_key] = [switch_id, in_port, out_port, flow, bytes, packets, minLatency, maxLatency, latency]

	def add(self, additional):
		# update flows
		for k, v in additional.flows.items():
			self.update_flow(k, *v)
		#update switches
		for k, v in additional.switches.items():
			self.update_switch(k, *v)

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

				for i in hops_metadata:
					key = "{} {} {} {}".format(i["switch_ID"], i["ingress_port"], i["egress_port"], flow)
					latency = i["latency"]
					state.update_switch(key, i["switch_ID"], i["ingress_port"], i["egress_port"], flow, packet_totalLen, 1,
										latency, latency, latency)
			
			except SendMetadata:
				# one packet may be incompletly added, so the more packets, the error is smaller
				# dictionaries must be copied to be sure that they are correctly serialized, because
				# serialization is performed by concurent thread
				# see https://stackoverflow.com/questions/28593103 
				tmp = copy.copy(state)
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

	# TODO: connect data from cmd line
	db = influxdb.InfluxDBClient(host='10.0.4.11', port=8086)

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
	
	start_measure = time.monotonic()
	try:
		while True:
			# wait a while
			time.sleep(5)

			for v in processes:
				os.kill(v.pid, signal.SIGINT)
			measure_time = time.monotonic() - start_measure
			start_measure = time.monotonic()
			
			final_result = ServerState()
			for v in results:
				c = v.get()
				final_result.add(c)
			
			if len(final_result.flows) == 0:
				continue

			print(final_result.flows)
			print("measure time: {} s".format(measure_time))
			# prepare final_result to the InfluxDB
			# spcace, coma and equal sign need to be escaped with \
			data = []
			for k, v in final_result.flows.items():
				data.append("flows,flow={flow} bytes={bytes},packets={pkts},minLantency={minLat},maxLantency={maxLat},avgLatency={avgLat}"
					.format(flow=k.replace(" ", "\ "),
							bytes=(v[0]/measure_time),
							pkts=(v[1]/measure_time),
							minLat=v[2],
							maxLat=v[3],
							avgLat=(v[4]/v[1])))
			
			for k, v in final_result.switches.items():
				data.append("switches,switchID={switchID},input={input},output={output},flow={flow} bytes={bytes},packets={pkts},minLantency={minLat},maxLantency={maxLat},avgLatency={avgLat}"
					.format(switchID=v[0],
							input=v[1],
							output=v[2],
							flow=v[3].replace(" ", "\ "),
							bytes=(v[4]/measure_time),
							pkts=(v[5]/measure_time),
							minLat=v[6],
							maxLat=v[7],
							avgLat=(v[8]/v[5])))
			# and finally send data to InfluxDB
			#print(data)
			db.write(data, {'db': 'int'}, protocol='line')
		
	except KeyboardInterrupt:
		pass

	finally:
		print("Shutting down...")

		# cleanup child process
		for v in processes:
			os.kill(v.pid, signal.SIGTERM)

		for v in processes:
			v.join()
