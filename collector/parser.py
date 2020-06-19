#!/usr/bin/env python3

import struct
import socket

def get_header_data(data, offset, size):
	if (offset + size > len(data)):
		raise Exception('Too short packet')
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
		raise Exception('Unknown IP version: {}'.format(ip_version))

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
		raise Exception('Unknown transport layer protocol')

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
		raise Exception('Invalid INT length')
	int_metadata = get_header_data(data, offset, header_size)

	return int_shim_header, int_header, int_metadata, ip_header, transport_header

def parse_int_report(data):
	int_shim_header, int_header, int_metadata, ip_header, transport_header = split_int_report(data)

	ip_version = get_ip_version(ip_header)

	srcIP = ''
	dstIP = ''
	if ip_version == 4:
		srcIP = socket.inet_ntop(socket.AF_INET, get_header_data(ip_header, 12, 4))
		dstIP = socket.inet_ntop(socket.AF_INET, get_header_data(ip_header, 16, 4))
	else:
		raise Exception('IPv{} not supported by report parser'.format(ip_version))

	srcPort = get_transport_port(get_header_data(data, 0, 2))
	dstPort = get_transport_port(get_header_data(data, 2, 2))

	print('Flow: {}:{} -> {}:{}'.format(srcIP, srcPort, dstIP, dstPort))

	# TODO: decode remaining important fields

	hop_ml = get_int_per_hop_metadata_size(int_header)
	print('Hop ML: {}'.format(hop_ml))
	if hop_ml == 0 or hop_ml > 10:
		raise Exception('Invalid per hop metadata len')
	if len(int_metadata) % hop_ml != 0:
		raise Exception('Invalid metadata len')

	instruction_set = get_int_instruction_set(int_header)

	hops_metadata = []
	metadata_set_offset = 0
	while metadata_set_offset < len(int_metadata):
		metadata_set = get_header_data(int_metadata, metadata_set_offset * 4, hop_ml * 4)
		metadata_set_offset += hop_ml

		metadata = {}
		offset = 0

		if instruction_set & (1 << 0):
			metadata[0] = get_int_dword(metadata_set, offset)
			offset = offset + 4
		else:
			metadata[0] = None
		
		# TODO: other metadata

		hops_metadata.append(metadata)
	
	return hops_metadata, srcIP, dstIP, srcPort, dstPort

def parse_int_report_fast_latency_one_hop(data):
	int_shim_header, int_header, int_metadata, ip_header, transport_header = split_int_report(data)

	return get_int_dword(int_metadata, 8)

def parse_int_report_fast_latency_two_hop(data):
	int_shim_header, int_header, int_metadata, ip_header, transport_header = split_int_report(data)

	hop_ml = 4 * get_int_per_hop_metadata_size(int_header)
	h1 = get_int_dword(int_metadata, 8)
	h2 = get_int_dword(int_metadata, hop_ml + 8)

	return h1 + h2
