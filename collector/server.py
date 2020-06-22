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
		self.pkts = 0
		self.totalDelay = 0
		self.minDelay = sys.maxsize
		self.maxDelay = 0


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
				#print("{} recv: ".format(os.getpid()), data)
			
				# decode packet and send to DB
				#parser.parse_int_report(data)
				#latency = parser.parse_int_report_fast_latency_one_hop(data)
				latency = parser.parse_int_report_fast_latency_two_hop(data)
				state.totalDelay += latency
				if latency < state.minDelay:
					state.minDelay = latency
				if latency > state.maxDelay:
					state.maxDelay = latency
				state.pkts += 1
			
			except SendMetadata:
				# one packet may be incompletly added, so the more packets, the error is smaller
				result.put_nowait(state)
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
				print("pkts: {}, delay min/max/total: {}/{}/{}".format(c.pkts, c.minDelay, c.maxDelay, c.totalDelay))
				final_result.pkts += c.pkts
				final_result.totalDelay += c.totalDelay
				if c.minDelay < final_result.minDelay:
					final_result.minDelay = c.minDelay
				if c.maxDelay > final_result.maxDelay:
					final_result.maxDelay = c.maxDelay

			if final_result.pkts != 0:
				print("pkts: {}, delay min/max/avg: {}/{}/{}".format(final_result.pkts, final_result.minDelay, final_result.maxDelay,
					final_result.totalDelay / final_result.pkts))
		
	except KeyboardInterrupt:
		pass

	print("Shutting down...")

	# cleanup child process
	for v in processes:
		os.kill(v.pid, signal.SIGTERM)

	for v in processes:
		v.join()
