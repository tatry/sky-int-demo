#!/usr/bin/env python3

import struct
import socket

class ParserError(Exception):
	pass

def get_header_data(data, offset, size):
	if (offset + size > len(data)):
		raise ParserError('Too short packet')
	return data[offset:offset+size]

def get_ip_version(data):
	return (struct.unpack('!B', get_header_data(data, 0, 1))[0] & 0xF0) >> 4

def get_transport_port(data):
	return struct.unpack('!H', data)[0]

def get_int_per_hop_metadata_size(data):
	return (struct.unpack('!B', get_header_data(data, 2, 1))[0] & 0x1F)

def get_int_instruction_set(data):
	return struct.unpack('!H', get_header_data(data, 4, 2))[0]

def get_int_word(data, offset):
	return struct.unpack('!H', get_header_data(data, offset, 2))[0]

def get_int_dword(data, offset):
	return struct.unpack('!I', get_header_data(data, offset, 4))[0]

def split_int_report(data):
	# data format in report is as follow:
	# IP (20/40 B), options ignored
	# TCP (20 B)/ UDP (8 B), options ignored
	# INT Shim (4 B)
	# INT (8 B)
	# INT metadata

	offset = 0

	# IP
	ip_version = get_ip_version(data)
	if ip_version == 4:
		header_size = 20
	elif ip_version == 6:
		header_size = 40
	else:
		raise ParserError('Unknown IP version: {}'.format(ip_version))

	ip_header = get_header_data(data, offset, header_size)
	offset += header_size

	next_protocol = struct.unpack('!B', get_header_data(ip_header, 9, 1))[0]
	
	# TCP/UDP
	transport_header = b''
	if next_protocol == 6:
		# TCP
		header_size = 20
		transport_header = get_header_data(data, offset, header_size)
		offset += header_size
	elif next_protocol == 17:
		# UDP
		header_size = 8
		transport_header = get_header_data(data, offset, header_size)
		offset += header_size
	else:
		raise ParserError('Unknown transport layer protocol')

	# INT shim
	header_size = 4
	int_shim_header = get_header_data(data, offset, header_size)
	offset += header_size

	# INT
	header_size = 8
	int_header = get_header_data(data, offset, header_size)
	offset += header_size

	# Metadata
	header_size = 4 * (get_header_data(int_shim_header, 2, 1)[0] - 3)
	if header_size < 0:
		raise ParserError('Invalid INT length')
	int_metadata = get_header_data(data, offset, header_size)

	return int_shim_header, int_header, int_metadata, ip_header, transport_header

def parse_int_report(data):
	int_shim_header, int_header, int_metadata, ip_header, transport_header = split_int_report(data)

	ip_version = get_ip_version(ip_header)

	# Decode flow

	srcIP = ''
	dstIP = ''
	packet_totalLen = 0
	if ip_version == 4:
		srcIP = socket.inet_ntop(socket.AF_INET, get_header_data(ip_header, 12, 4))
		dstIP = socket.inet_ntop(socket.AF_INET, get_header_data(ip_header, 16, 4))
		packet_totalLen = get_int_word(ip_header, 2)
	else:
		raise ParserError('IPv{} not supported by report parser'.format(ip_version))

	srcPort = get_transport_port(get_header_data(transport_header, 0, 2))
	dstPort = get_transport_port(get_header_data(transport_header, 2, 2))

	transport_protocol = ''
	if len(transport_header) == 20:
		transport_protocol = 'tcp'
	else:
		transport_protocol = 'udp'

	# Decode INT

	hop_ml = get_int_per_hop_metadata_size(int_header)
	if hop_ml != 10:
		raise ParserError('Invalid per hop metadata len. This demo assume that all metadata are collected')
	if len(int_metadata) % hop_ml != 0:
		raise ParserError('Invalid metadata len')

	hops_metadata = []
	metadata_set_offset = 0
	while metadata_set_offset < len(int_metadata):
		metadata_set = get_header_data(int_metadata, metadata_set_offset, hop_ml * 4)
		metadata_set_offset += 4 * hop_ml

		metadata = {}
		offset = 0

		# switch ID
		metadata["switch_ID"] = get_int_dword(metadata_set, offset)
		offset = offset + 4
		
		# ingress and egress port
		metadata["ingress_port"] = get_int_word(metadata_set, offset)
		offset = offset + 2
		metadata["egress_port"] = get_int_word(metadata_set, offset)
		offset = offset + 2

		# hop latency
		metadata["latency"] = get_int_dword(metadata_set, offset)
		offset = offset + 4

		# queue
		#offset = offset + 4

		# ingress timestamp
		#offset = offset + 4

		# egress timestamp
		#offset = offset + 4

		# logical input and output port
		#offset = offset + 4
		#offset = offset + 4

		# tx port utilization
		#offset = offset + 4

		# checksum complement
		#offset = offset + 4

		hops_metadata.append(metadata)
	
	return hops_metadata, transport_protocol, srcIP, dstIP, srcPort, dstPort, packet_totalLen

