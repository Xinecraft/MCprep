#!/usr/local/bin/python3
# Tool to pull down material names from jmc2obj and Mineways

import json
import os
import zipfile
import urllib.request
import xml.etree.ElementTree as ET

MINEWAYS_URL = "https://raw.githubusercontent.com/erich666/Mineways/master/Win/tiles.h"

# unused (here) mapping of block name IDs to materials/textures
# JMC_URL = "https://raw.githubusercontent.com/jmc2obj/j-mc-2-obj/master/conf/blocks.conf"

# could have multiple mappings, just use the latest here
JMC_1_13 = "https://raw.githubusercontent.com/jmc2obj/j-mc-2-obj/master/conf/texsplit_1.13.conf"


def save_file_str(url):
	"""Save to temp location next to script."""
	request = urllib.request.Request(url)
	result = urllib.request.urlopen(request)
	result_string = result.read()
	result.close()
	return result_string.decode()


def get_jmc2obj_list():
	"""Get the list of material names for jmc2obj"""
	raw_str = save_file_str(JMC_URL)
	root = ET.fromstring(raw_str)
	outlist = {}
	for block in root:
		mats = block.findall("materials")
		for itm in mats:
			materials = itm.text.split()
			outlist.update({sub.strip():None for sub in materials})
		# if mats:
		# 	outlist.update({itm.text:None for itm in mats})
	return outlist


def get_jmc2obj_mapping():
	"""Download the original texture mapping from the jmc2obj source code"""
	raw_str = save_file_str(JMC_1_13)
	root = ET.fromstring(raw_str)
	outlist = {}
	ln = len('assets/minecraft/textures/')

	for tex in root:
		src_tex = tex.get('name')
		jmc_tex = tex.getchildren()[0].get('name')

		if not src_tex.endswith('.png'):
			print("Not a png: "+src_tex)
			raise Exception("Src file is not a png")

		# note that block is not plural in this conf file, but is in tex packs
		if src_tex.startswith('assets/minecraft/textures/block/'):
			outlist[jmc_tex] = os.path.basename(src_tex)[:-4]
		elif src_tex.startswith('assets/minecraft/textures/'):
			outlist[jmc_tex] = src_tex[ln:-4]

		# so, if it stars with "assets/minecraft/textures/block/",
		# then truncate to just the basename
		# else, join one level up (ie entity instead of block, etc)
	return outlist


# def jmc2mc(name, vanilla):
# 	"""Function that attemtps to map jmc2obj texture name to canonical"""
# 	if name in vanilla:
# 		return name

# 	# general used vars for checks
# 	sub = name.split("_")

# 	def flipterm(name):
# 		name = name.replace("lower", "bottom")
# 		return name.replace("upper", "top")

# 	# just reverse the two phrases
# 	if len(sub) == 2:
# 		reverse = sub[-1] + "_" + sub[0]
# 		if reverse in vanilla:
# 			return reverse
# 		reverse = flipterm(reverse)
# 		if reverse in vanilla:
# 			return reverse

# 	# `door_birch_lower` to `birch_door_bottom`
# 	# or `door_dark_oak_upper` to `dark_oak_door_top`
# 	if "door" in name:
# 		if len(sub)>=3:
# 			recon = "{}_door_{}".format(
# 				"_".join(sub[1:-1]),
# 				sub[-1])
# 			if recon in vanilla:
# 				return recon
# 			termflip = flipterm(recon)
# 			if termflip in vanilla:
# 				return termflip

# 	# flip around e.g. `wool_light_blue` to `light_blue_wool`,
# 	# also applies to concrete and carpet
# 	prefix_to_suffix = "_".join(sub[1:-1]) + "_" + sub[-1]
# 	if prefix_to_suffix in vanilla:
# 		return prefix_to_suffix
# 	ps_termflip = flipterm(prefix_to_suffix)
# 	if ps_termflip in vanilla:
# 		return ps_termflip

# 	# e.g. `log_dark_oak_top` to `dark_oak_log_top`

# 	# if "carpet" in sub:
# 	# 	wool = name.replace("carpet", "wool")
# 	# 	if wool in vanilla:
# 	# 		return wool
# 	if "carpet" in name:
# 		wool = reverse.replace("carpet", "wool")
# 		if wool in vanilla:
# 			return wool

# 	if "glass" in name:
# 		name = name.replace("glass", "stained_glass")


# 	# for those we REALLY can't generalize, hard code mapping
# 	hmap = {
# 		"":""
# 	}
# 	if name in hmap and hmap[name] in vanilla:
# 		return hmap[name]

# 	if name+"_top" in vanilla:
# 		return name+"_top"

# 	# started with over 390/646, downed it to:
# 	return None


def get_mineways_list(vanilla):
	"""Get the list of material names for Mineways"""
	raw_str = save_file_str(MINEWAYS_URL) # for individual file-based mats
	outlist = {}

	# This is super low-level page parsing, will break if source code changes
	textblock = raw_str.split("} gTilesTable[TOTAL_TILES] = {")[1]
	textblock = textblock.split("};")[0]

	mats = []
	for line in textblock.split('\n'):
		if not ',' in line or not line.strip().startswith('{'):
			continue
		prename = line.split(',')[3]
		name = prename.split('"')[1] # go from  ' L"lectern_sides"'  to 'lectern_sides'
		presubname = line.split(',')[4]
		presubname = presubname.split('"')[1]
		if presubname:
			# print("YES!: ", presubname)
			name_sub = name+"_"+presubname
			if name_sub in vanilla:
				outlist[name_sub] = name_sub
				#mats.append(name_sub)
			elif name in vanilla:
				outlist[name] = name
				#mats.append(name)
			else:
				outlist[name.lower()] = name
				#mats.append(name.lower())
		else:
			if name in vanilla:
				outlist[name] = name
				#mats.append(name)
			else:
				outlist[name.lower()] = name
				#mats.append(name.lower()) # make it none?
	return outlist


def mineways2mc(name, vanilla):
	"""Function that attemtps to map Mineways texture name to canonical"""
	if name in vanilla:
		return name
	return None


def get_vanilla_list():
	"""Get the list of material names from vanilla Minecraft (local install)"""
	outlist = {}

	# OSX path
	path = os.path.join(
		os.path.expanduser('~'),
		"Library", "Application Support", "minecraft", "versions")
	if not os.path.isdir(path):
		raise Exception('Could not get vanilla path')

	versions = [ver for ver in os.listdir(path)
				if os.path.isdir(os.path.join(path, ver))]

	# turn into sortable tuples
	verion_tuples = []
	for ver in versions:
		temp = []
		for itm in ver.split('.'):
			try:
				temp.append(int(itm))
			except:
				break
		verion_tuples.append(tuple(temp))

	# parallel sort the list based on the generated tuple
	verion_tuples, versions = zip(*sorted(zip(verion_tuples, versions)))
	# print(versions)

	jarfile = None
	for i, ver in reversed(list(enumerate(verion_tuples))):
		ver_folder = os.path.join(path, versions[i])
		any_jar = [jar for jar in os.listdir(ver_folder)
			if jar.lower().endswith('.jar')]
		if any_jar:
			jarfile = os.path.join(path, versions[i], any_jar[0])
			break

	if not jarfile:
		raise Exception("Could not get most recent jar version")

	print("Got jar version: {}".format(os.path.basename(jarfile)))
	archive = zipfile.ZipFile(jarfile, 'r')
	prefix = 'assets/minecraft/textures/'

	for name in archive.namelist():
		if not name.endswith('.png'):
			continue
		base = os.path.basename(name)[:-4]

		if name.startswith(prefix+"block"):
			outlist[base] = base
		elif name.startswith(prefix): # at least in textures folder
			outlist[base] = name[len(prefix):-4]
		else:
			outlist[base] = None
			# print("Not in textures folder: "+name)
			# mostly just "realms" stuff

	archive.close()
	return outlist


def get_current_json(backup=False):
	"""Returns filepath of current json"""
	suffix = "" if not backup else "backup"
	filepath = os.path.join(
		"MCprep_addon", "MCprep_resources",
		"mcprep_data_update"+suffix+".json")
	return filepath


def read_base_mapping():
	"""Read in the existing mcprep_data_update.json file shipped with MCprep"""
	filepath = "mcprep_data_base.json"
	if not os.path.isfile(filepath):
		raise Exception("File missing: "+filepath)

	with open(filepath, 'r') as rawfile:
		data = json.load(rawfile)
	return data


def run_all(auto=False):
	"""Execute getting all of the texture lists and to compare."""

	data = {"blocks": {}}

	# loads in existing resource json, for truly hand-stated things
	base_override = read_base_mapping()

	# consider also passing in pref to get specific version, for old names
	vanilla = get_vanilla_list()

	# load material lists from online blobs
	jmc = get_jmc2obj_mapping()
	mineways = get_mineways_list(vanilla)

	# load the hard-coded lists
	# hard_coded = ["reflective", "water", "emit", "desaturated",
	# 	"animated_mineways_index", "solid", "metallic"]
	# for setname in hard_coded:
	# 	data["blocks"] = {}
	# 	data["blocks"][setname] = existing["blocks"].get(setname)

	# now update the main blocks with the known mappings only
	# already exact, but could do cross check for any current MC canonical missing
	data["blocks"]["block_mapping_jmc"] = jmc

	# data["blocks"]["block_mapping_jmc"] = {
	# 	mat:jmc2mc(mat, vanilla) for mat in jmc
	# 	if jmc2mc(mat, vanilla) is not None}
	data["blocks"]["block_mapping_mineways"] = mineways
	# data["blocks"]["block_mapping_mineways"] = {
	# 	mat:mineways2mc(mat, vanilla) for mat in mineways
	# 	if mineways2mc(mat, vanilla) is not None}

	data["blocks"].update(base_override["blocks"])

	vanilla_blocks = [vanilla[itm] for itm in vanilla
			if itm is not None
			and vanilla[itm] is not None
			and ("/" not in vanilla[itm] or vanilla[itm].startswith("blocks"))]

	bl = data["blocks"]
	print_str = """Found the following:
	{jmc} jmc2obj blocks
	{mine} Mineways blocks
	{MC} mc textures,
	{BLK} are blocks
	""".format(
		jmc=len(bl["block_mapping_jmc"]),
		mine=len(bl["block_mapping_mineways"]),
		MC=len(vanilla),
		BLK=len(vanilla_blocks))
	print(print_str)
	# same for the other two..

	# Goal: generate, best we can, the actual mapping file to use for materials

	# save the output
	fileout = "mcprep_data_update_staging.json"
	fileout = os.path.abspath(fileout)
	with open(fileout, "w") as dmp:
		json.dump(data, dmp, indent="\t", sort_keys=True)
	print("Output file:")
	print(fileout)

	if auto:
		xin = "y"
	else:
		xin = input("Show missing jmc2obj mappings? (y): ")
	if xin == "y":
		print("PRINTING jmc2obj MATERIALS WITH NO VANILLA MAPPING")
		miss = [itm for itm in jmc
			if os.path.basename(jmc[itm]) not in vanilla]
		for itm in sorted(miss):
			print("\t"+itm)
		print("Total miss {}, versus {} total".format(
			len(miss), len(jmc)))

		# now, find how many vanilla textures are NOT in jmc2obj
		print("PRINTING vanilla MATERIALS NOT IN JMC2OBJ")
		jmc_v = [jmc[itm] for itm in jmc]
		miss = [vanilla[itm] for itm in vanilla
			if itm not in jmc_v
			and vanilla[itm] is not None
			and ("/" not in vanilla[itm] or vanilla[itm].startswith("blocks"))]
		for itm in sorted(miss):
			print("\t"+itm)
		print("Total miss {}, versus {} (blocks only)".format(
			len(miss), len(vanilla_blocks)))

	if auto:
		xin = "y"
	else:
		xin = input("Show missing Mineways mappings? (y): ")
	if xin == "y":
		print("PRINTING mineways MISSED MATERIALS")
		miss = [itm for itm in mineways
			if not mineways[itm]
			or os.path.basename(mineways[itm]) not in vanilla]
		for itm in sorted(miss):
			print("\t"+itm)
		print("\tTotal miss {}, versus {} total".format(
			len(miss), len(mineways)))

		# now, find how many vanilla textures are NOT in jmc2obj
		print("PRINTING vanilla MATERIALS NOT IN MINEWAYS")
		minew_v = [mineways[itm] for itm in mineways]
		miss = [vanilla[itm] for itm in vanilla
			if itm not in minew_v
			and vanilla[itm] is not None
			and ("/" not in vanilla[itm] or vanilla[itm].startswith("blocks"))]
		for itm in sorted(miss):
			print("\t"+itm)
		print("Total miss {}, versus {} (blocks only)".format(
			len(miss), len(vanilla_blocks)))

	if auto:
		xin = "y"
	else:
		xin = input("Replace current mapping file? (y): ")
	if xin == "y":
		main_file = get_current_json()
		bup_file = get_current_json(backup=True)
		if os.path.isfile(bup_file):
			os.remove(bup_file)
		os.rename(fileout, main_file)
		print("Replaced file: "+main_file)


if __name__ == '__main__':
	run_all()