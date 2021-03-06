# ##### MCprep #####
#
# Developed by Patrick W. Crawford, see more at
# http://theduckcow.com/dev/blender/MCprep
#
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


import bpy
import traceback

import os
import json
import sys
import io
from contextlib import redirect_stdout
import importlib
import tempfile
import shutil
from mathutils import Vector

TEST_FILE = "test_results.tsv"

# -----------------------------------------------------------------------------
# Primary test loop
# -----------------------------------------------------------------------------


class mcprep_testing():
	# {status}, func, prefunc caller (reference only)

	def __init__(self):
		self.suppress = True # hold stdout
		self.test_status = {} # {func.__name__: {"check":-1, "res":-1,0,1}}
		self.test_cases = [
			self.enable_mcprep,
			self.prep_materials,
			self.openfolder,
			self.spawn_mob,
			self.change_skin,
			self.import_world_split,
			self.import_world_fail,
			self.import_jmc2obj,
			self.import_mineways_separated,
			self.import_mineways_combined,
			self.name_generalize,
			self.meshswap_spawner,
			self.meshswap_jmc2obj,
			self.meshswap_mineways_separated,
			self.meshswap_mineways_combined,
			self.detect_desaturated_images,
			self.find_missing_images_cycles,
			self.qa_meshswap_file,
			self.item_spawner,
			self.world_tools,
			]
		self.run_only = None # name to give to only run this test

		self.mcprep_json = {}
		# 	1:["combine_materials", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	2:["combine_images", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	3:["scale_uv", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	4:["isolate_alpha_uvs", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	9:["fix_skin_eyes", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	10:["add_skin", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	11:["remove_skin", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	12:["reload_skins", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	14:["handler_skins_enablehack", {"type":"material","check":0,"res":""}, ""],
		# 	16:["openfolder", {"type":"mcprep_ui","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["meshswap_pathreset", {"type":"meshswap","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["meshswap_spawner", {"type":"meshswap","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["reload_meshswap", {"type":"meshswap","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["fixmeshswapsize", {"type":"meshswap","check":0,"res":""}, "bpy.ops.object"],
		# 	16:["reload_spawners", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["reload_mobs", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["mob_spawner_direct", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["mob_spawner", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["mob_install_menu", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# }

	def run_all_tests(self):
		"""For use in command line mode, run all tests and checks"""
		if self.run_only and self.run_only not in [tst.__name__ for tst in self.test_cases]:
			print("{}No tests ran!{} Test function not found: {}".format(
				COL.FAIL, COL.ENDC, self.run_only))

		for test in self.test_cases:
			if self.run_only and test.__name__ != self.run_only:
				continue
			self.mcrprep_run_test(test)

		failed_tests = [tst for tst in self.test_status
			if self.test_status[tst]["check"] < 0]
		passed_tests = [tst for tst in self.test_status
			if self.test_status[tst]["check"] > 0]

		print("\n{}COMPLETED, {} passed and {} failed{}".format(
			COL.HEADER,
			len(passed_tests), len(failed_tests),
			COL.ENDC))
		if passed_tests:
			print("{}Passed tests:{}".format(COL.OKGREEN, COL.ENDC))
			print("\t"+", ".join(passed_tests))
		if failed_tests:
			print("{}Failed tests:{}".format(COL.FAIL, COL.ENDC))
			for tst in self.test_status:
				if self.test_status[tst]["check"] > 0:
					continue
				ert = suffix_chars(self.test_status[tst]["res"], 70)
				print("\t{}{}{}: {}".format(COL.UNDERLINE, tst, COL.ENDC, ert))

		# indicate if all tests passed for this blender version
		if not failed_tests:
			with open(TEST_FILE, 'a') as tsv:
				tsv.write("{}\t{}\t-\n".format(bpy.app.version, "ALL PASSED"))

	def write_placeholder(self, test_name):
		"""Append placeholder, presuming if not changed then blender crashed"""
		with open(TEST_FILE, 'a') as tsv:
			tsv.write("{}\t{}\t-\n".format(
				bpy.app.version, "CRASH during "+test_name))

	def update_placeholder(self, test_name, test_failure):
		"""Update text of (if error) or remove placeholder row of file"""
		with open(TEST_FILE, 'r') as tsv:
			contents = tsv.readlines()

		if not test_failure: # None or ""
			contents = contents[:-1]
		else:
			this_failure = "{}\t{}\t{}\n".format(
				bpy.app.version, test_name, suffix_chars(test_failure, 20))
			contents[-1] = this_failure
		with open(TEST_FILE, 'w') as tsv:
			for row in contents:
				tsv.write(row)

	def mcrprep_run_test(self, test_func):
		"""Run a single MCprep test"""
		print("\n{}Testing {}{}".format(COL.HEADER, test_func.__name__, COL.ENDC))
		self.write_placeholder(test_func.__name__)
		self._clear_scene()
		try:
			if self.suppress:
				stdout = io.StringIO()
				with redirect_stdout(stdout):
					res = test_func()
			else:
				res = test_func()
			if not res:
				print("\t{}TEST PASSED{}".format(COL.OKGREEN, COL.ENDC))
				self.test_status[test_func.__name__] = {"check":1, "res": res}
			else:
				print("\t{}TEST FAILED:{}".format(COL.FAIL, COL.ENDC))
				print("\t"+res)
				self.test_status[test_func.__name__] = {"check":-1, "res": res}
		except Exception as e:
			print("\t{}TEST FAILED{}".format(COL.FAIL, COL.ENDC))
			print(traceback.format_exc()) # plus other info, e.g. line number/file?
			res = traceback.format_exc()
			self.test_status[test_func.__name__] = {"check":-1, "res": res}
		# print("\tFinished test {}".format(test_func.__name__))
		self.update_placeholder(test_func.__name__, res)

	def setup_env_paths(self):
		"""Adds the MCprep installed addon path to sys for easier importing."""
		to_add = None

		for base in bpy.utils.script_paths():
			init = os.path.join(base, "addons", "MCprep_addon", "__init__.py")
			if os.path.isfile(init):
				to_add = init
				break
		if not to_add:
			raise Exception("Could not add the environment path for direct importing")

		# add to path and bind so it can use relative improts (3.5 trick)
		spec = importlib.util.spec_from_file_location("MCprep", to_add)
		module = importlib.util.module_from_spec(spec)
		sys.modules[spec.name] = module
		spec.loader.exec_module(module)

		from MCprep import conf
		conf.init()

	def get_mcprep_path(self):
		"""Returns the addon basepath installed in this blender instance"""
		for base in bpy.utils.script_paths():
			init = os.path.join(base, "addons", "MCprep_addon") # __init__.py folder
			if os.path.isdir(init):
				return init
		return None



	# -----------------------------------------------------------------------------
	# Testing utilities, not tests themselves (ie assumed to work)
	# -----------------------------------------------------------------------------

	def _clear_scene(self):
		"""Clear scene and data without printouts"""
		# if not self.suppress:
		# stdout = io.StringIO()
		# with redirect_stdout(stdout):
		bpy.ops.wm.read_homefile(app_template="")
		for obj in bpy.data.objects:
			bpy.data.objects.remove(obj) # wait, that's illegal?
		for mat in bpy.data.materials:
			bpy.data.materials.remove(mat)
			# for txt in bpy.data.texts:
			# 	bpy.data.texts.remove(txt)

	def _add_character(self):
		"""Add a rigged character to the scene, specifically Alex"""
		bpy.ops.mcprep.reload_mobs()
		# mcmob_type='player/Simple Rig - Boxscape-TheDuckCow.blend:/:Simple Player'
		# mcmob_type='player/Alex FancyFeet - TheDuckCow & VanguardEnni.blend:/:alex'
		mcmob_type='hostile/mobs - Rymdnisse.blend:/:silverfish'
		bpy.ops.mcprep.mob_spawner(mcmob_type=mcmob_type)

	def _import_jmc2obj_full(self):
		"""Import the full jmc2obj test set"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(testdir, "jmc2obj", "jmc2obj_test_1_15_2.obj")
		bpy.ops.mcprep.import_world_split(filepath=obj_path)

	def _import_mineways_separated(self):
		"""Import the full jmc2obj test set"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(testdir, "mineways", "separated_textures",
			"mineways_test_separated_1_15_2.obj")
		bpy.ops.mcprep.import_world_split(filepath=obj_path)

	def _import_mineways_combined(self):
		"""Import the full jmc2obj test set"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(testdir, "mineways", "combined_textures",
			"mineways_test_combined_1_15_2.obj")
		bpy.ops.mcprep.import_world_split(filepath=obj_path)

	def _create_canon_mat(self, canon=None):
		"""Creates a material that should be recognized"""
		name = canon if canon else "dirt"
		mat = bpy.data.materials.new(name)
		mat.use_nodes = True
		img_node = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
		if canon:
			base = self.get_mcprep_path()
			filepath = os.path.join(base, "MCprep_resources",
				"resourcepacks", "mcprep_default", "assets", "minecraft", "textures",
				"block", canon+".png")
			img = bpy.data.images.load(filepath)
		else:
			img = bpy.data.images.new(name, 16, 16)
		img_node.image = img
		return mat, img_node

	# Seems that infolog doesn't update in background mode
	def _get_last_infolog(self):
		"""Return back the latest info window log"""
		for txt in bpy.data.texts:
			bpy.data.texts.remove(txt)
		res = bpy.ops.ui.reports_to_textblock()
		print("DEVVVV get last infolog:")
		for ln in bpy.data.texts['Recent Reports'].lines:
			print(ln.body)
		print("END printlines")
		return bpy.data.texts['Recent Reports'].lines[-1].body

	def _set_exporter(self, name):
		"""Sets the exporter name"""
		if name not in ['(choose)', 'jmc2obj', 'Mineways']:
			raise Exception('Invalid exporter set tyep')
		from MCprep.util import get_user_preferences
		context = bpy.context
		if hasattr(context, "user_preferences"):
			prefs = context.user_preferences.addons.get("MCprep_addon", None)
		elif hasattr(context, "preferences"):
			prefs = context.preferences.addons.get("MCprep_addon", None)
		prefs.preferences.MCprep_exporter_type = name


	# -----------------------------------------------------------------------------
	# Operator unit tests
	# -----------------------------------------------------------------------------

	def enable_mcprep(self):
		"""Ensure we can both enable and disable MCprep"""

		# brute force enable
		# stdout = io.StringIO()
		# with redirect_stdout(stdout):
		try:
			if hasattr(bpy.ops, "preferences") and "addon_enable" in dir(bpy.ops.preferences):
				bpy.ops.preferences.addon_enable(module="MCprep_addon")
			else:
				bpy.ops.wm.addon_enable(module="MCprep_addon")
		except:
			pass

		# see if we can safely toggle off and back on
		if hasattr(bpy.ops, "preferences") and "addon_enable" in dir(bpy.ops.preferences):
			bpy.ops.preferences.addon_disable(module="MCprep_addon")
			bpy.ops.preferences.addon_enable(module="MCprep_addon")
		else:
			bpy.ops.wm.addon_disable(module="MCprep_addon")
			bpy.ops.wm.addon_enable(module="MCprep_addon")

	def prep_materials(self):
		# run once when nothing is selected, no active object
		self._clear_scene()


		# res = bpy.ops.mcprep.prep_materials(
		# 	animateTextures=False,
		# 	autoFindMissingTextures=False,
		# 	improveUiSettings=False,
		# 	)
		# if res != {'CANCELLED'}:
		# 	return "Should have returned cancelled as no objects selected"
		# elif "No objects selected" != self._get_last_infolog():
		# 	return "Did not get the right info log back"

		status = 'fail'
		print("Checking blank usage")
		try:
			bpy.ops.mcprep.prep_materials(
				animateTextures=False,
				autoFindMissingTextures=False,
				improveUiSettings=False
				)
		except RuntimeError as e:
			if "Error: No objects selected" in str(e):
				status = 'success'
			else:
				return "prep_materials other err: "+str(e)
		if status=='fail':
			return "Prep should have failed with error on no objects"

		# add object, no material. Should still fail as no materials
		bpy.ops.mesh.primitive_plane_add()
		obj = bpy.context.object
		status = 'fail'
		try:
			res = bpy.ops.mcprep.prep_materials(
				animateTextures=False,
				autoFindMissingTextures=False,
				improveUiSettings=False)
		except RuntimeError as e:
			if 'No materials found' in str(e):
				status = 'success' # expect to fail when nothing selected
		if status=='fail':
			return "mcprep.prep_materials-02 failure"

		# TODO: Add test where material is added but without an image/nodes

		# add object with canonical material name. Assume cycles
		new_mat, _ = self._create_canon_mat()
		obj.active_material = new_mat
		status = 'fail'
		try:
			res = bpy.ops.mcprep.prep_materials(
				animateTextures=False,
				autoFindMissingTextures=False,
				improveUiSettings=False)
		except Exception as e:
			return "Unexpected error: "+str(e)
		# how to tell if prepping actually occured? Should say 1 material prepped
		# print(self._get_last_infolog()) # error in 2.82+, not used anyways

	def prep_materials_cycles(self):
		"""Cycles-specific tests"""

	def find_missing_images_cycles(self):
		"""Find missing images from selected materials, cycles.

		Scenarios in which we find new textures
		One: material is empty with no image block assigned at all, though has
			 image node and material is a canonical name
		Two: material has image block but the filepath is missing, find it
		Three: image is there, or image is packed; ie assume is fine (don't change)
		"""

		# first, import a material that has no filepath
		self._clear_scene()
		mat, node = self._create_canon_mat("sugar_cane")
		bpy.ops.mesh.primitive_plane_add()
		bpy.context.object.active_material = mat

		pre_path = node.image.filepath
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		post_path = node.image.filepath
		canonical_path = post_path # save for later
		if pre_path != post_path:
			return "Pre/post path differed, should be the same"

		# now save the texturefile somewhere
		tmp_dir = tempfile.gettempdir()
		tmp_image = os.path.join(tmp_dir, "sugar_cane.png")
		shutil.copyfile(node.image.filepath, tmp_image) # leave original in tact

		# Test that path is unchanged even when with a non canonical path
		node.image.filepath = tmp_image
		if node.image.filepath != tmp_image:
			os.remove(tmp_image)
			return "fialed to setup test, node path not = "+tmp_image
		pre_path = node.image.filepath
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		post_path = node.image.filepath
		if pre_path != post_path:
			os.remove(tmp_image)
			return "Pre/post path differed in tmp dir when there should have been no change: pre {} vs post {}".format(
				pre_path, post_path)

		# test that an empty node within a canonically named material is fixed
		pre_path = node.image.filepath
		node.image = None # remove the image from block
		if node.image:
			os.remove(tmp_image)
			return "failed to setup test, image block still assigned"
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		post_path = node.image.filepath
		if not post_path:
			os.remove(tmp_image)
			return "No post path found, should have loaded file"
		elif post_path == pre_path:
			os.remove(tmp_image)
			return "Should have loaded image as new datablock from canon location"
		elif not os.path.isfile(post_path):
			os.remove(tmp_image)
			return "New path file does not exist"

		# test an image with broken texturepath is fixed for cannon material name

		# node.image.filepath = tmp_image # assert it's not the canonical path
		# pre_path = node.image.filepath # the original path before renaming
		# os.rename(tmp_image, tmp_image+"x")
		# if os.path.isfile(bpy.path.abspath(node.image.filepath)) or pre_path != node.image.filepath:
		# 	os.remove(pre_path)
		# 	os.remove(tmp_image+"x")
		# 	return "Failed to setup test, original file exists/img path updated"
		# bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		# post_path = node.image.filepath
		# if pre_path == post_path:
		# 	os.remove(tmp_image+"x")
		# 	return "Should have updated missing image to canonical, still is "+post_path
		# elif post_path != canonical_path:
		# 	os.remove(tmp_image+"x")
		# 	return "New path not canonical: "+post_path
		# os.rename(tmp_image+"x", tmp_image)

		# Example where we save and close the blend file, move the file,
		# and re-open. First, load the scene
		self._clear_scene()
		mat, node = self._create_canon_mat("sugar_cane")
		bpy.ops.mesh.primitive_plane_add()
		bpy.context.object.active_material = mat
		# Then, create the textures locally
		bpy.ops.file.pack_all()
		bpy.ops.file.unpack_all(method='USE_LOCAL')
		unpacked_path = bpy.path.abspath(node.image.filepath)
		# close and open, moving the file in the meantime
		save_tmp_file = os.path.join(tmp_dir, "tmp_test.blend")
		os.rename(unpacked_path, unpacked_path+"x")
		bpy.ops.wm.save_mainfile(filepath=save_tmp_file)
		bpy.ops.wm.open_mainfile(filepath=save_tmp_file)
		# now run the operator
		img = bpy.data.images['sugar_cane.png']
		pre_path = img.filepath
		if os.path.isfile(pre_path):
			os.remove(unpacked_path+"x")
			return "Failed to setup test for save/reopn move"
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		post_path = img.filepath
		if post_path == pre_path:
			os.remove(unpacked_path+"x")
			return "Did not change path from "+pre_path
		elif not os.path.isfile(post_path):
			os.remove(unpacked_path+"x")
			return "File for blend reloaded image does not exist: "+node.image.filepath
		os.remove(unpacked_path+"x")

		# address the example of sugar_cane.png.001 not being detected as canonical
		# as a front-end name (not image file)
		self._clear_scene()
		mat, node = self._create_canon_mat("sugar_cane")
		bpy.ops.mesh.primitive_plane_add()
		bpy.context.object.active_material = mat

		pre_path = node.image.filepath
		node.image = None # remove the image from block
		mat.name = "sugar_cane.png.001"
		if node.image:
			os.remove(tmp_image)
			return "failed to setup test, image block still assigned"
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		if not node.image:
			os.remove(tmp_image)
			return "Failed to load new image within mat named .png.001"
		post_path = node.image.filepath
		if not post_path:
			os.remove(tmp_image)
			return "No image loaded for "+mat.name
		elif not os.path.isfile(node.image.filepath):
			return "File for loaded image does not exist: "+node.image.filepath

		# Example running with animateTextures too

		# check on image that is packed or not, or packed but no data
		os.remove(tmp_image)


	def openfolder(self):
		if bpy.app.background is True:
			return "" # can't test this in background mode

		folder = bpy.utils.script_path_user()
		if not os.path.isdir(folder):
			return "Sample folder doesn't exist, couldn't test"
		res = bpy.ops.mcprep.openfolder(folder)
		if res=={"FINISHED"}:
			return ""
		else:
			return "Failed, returned cancelled"

	def spawn_mob(self):
		"""Spawn mobs, reload mobs, etc"""
		self._clear_scene()
		self._add_character() # run the utility as it's own sort of test

		self._clear_scene()
		bpy.ops.mcprep.reload_mobs()

		# sample don't specify mob, just load whatever is first
		bpy.ops.mcprep.mob_spawner()

		# spawn an alex

		# try changing the folder

		# try install mob and uninstall

	def change_skin(self):
		"""Test scenarios for changing skin after adding a character."""
		self._clear_scene()

		bpy.ops.mcprep.reload_skins()
		skin_ind = bpy.context.scene.mcprep_skins_list_index
		skin_item = bpy.context.scene.mcprep_skins_list[skin_ind]
		tex_name = skin_item['name']
		skin_path = os.path.join(bpy.context.scene.mcprep_skin_path, tex_name)

		status = 'fail'
		try:
			res = bpy.ops.mcprep.applyskin(
			filepath=skin_path,
			new_material=False)
		except RuntimeError as e:
			if 'No materials found to update' in str(e):
				status = 'success' # expect to fail when nothing selected
		if status=='fail':
			return "Should have failed to skin swap with no objects selected"

		# now run on a real test character, with 1 material and 2 objects
		self._add_character()

		pre_mats = len(bpy.data.materials)
		bpy.ops.mcprep.applyskin(
			filepath=skin_path,
			new_material=False)
		post_mats = len(bpy.data.materials)
		if post_mats != pre_mats: # should be unchanged
			return "change_skin.mat counts diff despit no new mat request, {} before and {} after".format(
				pre_mats, post_mats)

		# do counts of materials before and after to ensure they match
		pre_mats = len(bpy.data.materials)
		bpy.ops.mcprep.applyskin(
			filepath=skin_path,
			new_material=True)
		post_mats = len(bpy.data.materials)
		if post_mats != pre_mats*2: # should exactly double since in new scene
			return "change_skin.mat counts diff mat counts, {} before and {} after".format(
				pre_mats, post_mats)

		pre_mats = len(bpy.data.materials)

		bpy.ops.mcprep.skin_swapper( # not diff operator name, this is popup browser
			filepath=skin_path,
			new_material=False)
		post_mats = len(bpy.data.materials)
		if post_mats != pre_mats: # should be unchanged
			return "change_skin.mat counts differ even though should be same, {} before and {} after".format(
				pre_mats, post_mats)

		# TODO: Add test for when there is a bogus filename, responds with
		# Image file not found in err

		# capture info or recent out?
		# check that username was there before or not
		bpy.ops.mcprep.applyusernameskin(
			username='TheDuckCow',
			skip_redownload=False,
			new_material=True)

		# check that timestamp of last edit of file was longer ago than above cmd

		bpy.ops.mcprep.applyusernameskin(
			username='TheDuckCow',
			skip_redownload=True,
			new_material=True)

		# test deleting username skin and that file is indeed deleted
		# and not in list anymore

		# bpy.ops.mcprep.applyusernameskin(
		# 	username='TheDuckCow',
		# 	skip_redownload=True,
		# 	new_material=True)

		# test that the file was added back

		bpy.ops.mcprep.spawn_with_skin()
		# test changing skin to file when no existing images/textres
		# test changing skin to file when existing material
		# test changing skin to file for both above, cycles and internal
		# test changing skin file for both above without, then with,
		#   then without again, normals + spec etc.
		return

	def import_world_split(self):
		"""Test that imported world has multiple objects"""
		self._clear_scene()

		pre_objects = len(bpy.data.objects)
		self._import_jmc2obj_full()
		post_objects = len(bpy.data.objects)
		if post_objects+1 > pre_objects:
			print("Success, had {} objs, post import {}".format(
				pre_objects, post_objects))
			return
		elif post_objects+1 == pre_objects:
			return "Only one new object imported"
		else:
			return "Nothing imported"

	def import_world_fail(self):
		"""Ensure loader fails if an invalid path is loaded"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(testdir, "jmc2obj", "xx_jmc2obj_test_1_14_4.obj")
		try:
			bpy.ops.mcprep.import_world_split(filepath=obj_path)
		except Exception as e:
			print("Failed, as intended: "+str(e))
			return
		return "World import should have returned an error"

	def import_materials_util(self, mapping_set):
		"""Reusable function for testing on different obj setups"""
		from MCprep.materials.generate import get_mc_canonical_name
		from MCprep.materials.generate import find_from_texturepack
		from MCprep import util
		from MCprep import conf

		util.load_mcprep_json() # force load json cache
		mcprep_data = conf.json_data["blocks"][mapping_set]

		# first detect alignment to the raw underlining mappings, nothing to
		# do with canonical yet
		mapped = [mat.name for mat in bpy.data.materials
			if mat.name in mcprep_data] # ok!
		unmapped = [mat.name for mat in bpy.data.materials
			if mat.name not in mcprep_data] # not ok
		fullset = mapped+unmapped # ie all materials
		unleveraged = [mat for mat in mcprep_data
			if mat not in fullset] # not ideal, means maybe missed check

		print("Mapped: {}, unmapped: {}, unleveraged: {}".format(
			len(mapped), len(unmapped), len(unleveraged)))

		if len(unmapped):
			err = "Textures not mapped to json file"
			print(err)
			print(sorted(unmapped))
			print("")
			#return err
		if len(unleveraged) > 20:
			err = "Json file materials not found in obj test file, may need to update world"
			print(err)
			print(sorted(unleveraged))
			# return err

		if len(mapped) == 0:
			return "No materials mapped"
		elif len(mapped) < len(unmapped): # +len(unleveraged), too many esp. for Mineways
			# not a very optimistic threshold, but better than none
			return "More materials unmapped than mapped"
		print("")

		mc_count=0
		jmc_count=0
		mineways_count=0

		# each element is [cannon_name, form], form is none if not matched
		mapped = [get_mc_canonical_name(mat.name) for mat in bpy.data.materials]

		# no matching canon name (warn)
		mats_not_canon = [itm[0] for itm in mapped if itm[1] is None]
		if mats_not_canon:
			print("Non-canon material names found: ({})".format(len(mats_not_canon)))
			print(mats_not_canon)
			if len(mats_not_canon)>30: # arbitrary threshold
				return "Too many materials found without canonical name ({})".format(
					len(mats_not_canon))
		else:
			print("Confirmed - no non-canon images found")

		# affirm the correct mappings
		mats_no_packimage = [find_from_texturepack(itm[0]) for itm in mapped
			if itm[1] is not None]
		mats_no_packimage = [path for path in mats_no_packimage if path]
		print("Mapped paths: "+str(len(mats_no_packimage)))

		# could not resolve image from resource pack (warn) even though in mapping
		mats_no_packimage = [itm[0] for itm in mapped
			if itm[1] is not None and not find_from_texturepack(itm[0])]
		print("No resource images found for mapped items: ({})".format(
			len(mats_no_packimage)))
		print("These would appear to have cannon mappings, but then fail on lookup")
		for itm in mats_no_packimage:
			print("\t"+itm)
		if len(mats_no_packimage)>5: # known number up front, e.g. chests, stone_slab_side, stone_slab_top
			return "Missing images for blocks specified in mcprep_data.json"

		# also test that there are not raw image names not in mapping list
		# but that otherwise could be added to the mapping list as file exists

	def import_jmc2obj(self):
		"""Checks that material names in output obj match the mapping file"""
		self._clear_scene()
		self._import_jmc2obj_full()

		res = self.import_materials_util("block_mapping_jmc")
		return res

	def import_mineways_separated(self):
		"""Checks Mineways (multi-image) material name mapping to mcprep_data"""
		self._clear_scene()
		self._import_mineways_separated()

		#mcprep_data = self._get_mcprep_data()
		res = self.import_materials_util("block_mapping_mineways")
		return res

	def import_mineways_combined(self):
		"""Checks Mineways (multi-image) material name mapping to mcprep_data"""
		self._clear_scene()
		self._import_mineways_combined()

		#mcprep_data = self._get_mcprep_data()
		res = self.import_materials_util("block_mapping_mineways")
		return res

	def name_generalize(self):
		"""Tests the outputs of the generalize function"""
		from MCprep.util import nameGeneralize
		test_sets = {
			"ab":"ab",
			"table.001":"table",
			"table.100":"table",
			"table001":"table001",
			"fire_0":"fire_0",
			# "fire_0_0001.png":"fire_0", not current behavior, but desired?
			"fire_0_0001":"fire_0",
			"fire_0_0001.001":"fire_0",
			"fire_layer_1":"fire_layer_1",
			"cartography_table_side1":"cartography_table_side1"
		}
		errors = []
		for key in list(test_sets):
			res = nameGeneralize(key)
			if res != test_sets[key]:
				errors.append("{} converts to {} and should be {}".format(
					key, res, test_sets[key]))
			else:
				print("{}:{} passed".format(key, res))

		if errors:
			return "Generalize failed: "+", ".join(errors)

	def meshswap_util(self, mat_name):
		"""Run meshswap on the first object with found mat_name"""
		if mat_name not in bpy.data.materials:
			return "Not a material: "+mat_name
		print("\nAttempt meshswap of "+mat_name)
		mat = bpy.data.materials[mat_name]

		obj = None
		for ob in bpy.data.objects:
			for slot in ob.material_slots:
				if slot and slot.material == mat:
					obj = ob
					break
			if obj:
				break
		if not obj:
			return "Failed to find obj for "+mat_name
		print("Found the object - "+obj.name)

		from MCprep.util import select_set
		bpy.ops.object.select_all(action='DESELECT')
		select_set(obj, True)
		res = bpy.ops.mcprep.meshswap()
		if res != {'FINISHED'}:
			return "Meshswap returned cancelled for "+mat_name

	def meshswap_spawner(self):
		"""Tests direct meshswap spawning"""
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props
		bpy.ops.mcprep.reload_meshswap()
		if not scn_props.meshswap_list:
			return "No meshswap assets loaded for spawning"
		elif len(scn_props.meshswap_list)<15:
			return "Too few meshswap assets available"

		if bpy.app.version >= (2, 80):
			# Add with make real = False
			bpy.ops.mcprep.meshswap_spawner(block='Collection/banner', make_real=False)

			# test doing two of the same one (first won't be cached, second will)
			# Add one with make real = True
			bpy.ops.mcprep.meshswap_spawner(block='Collection/fire', make_real=True)
			if 'fire' not in bpy.data.collections:
				return "Fire not in collections"
			elif not bpy.context.selected_objects:
				return "Added made-real meshswap objects not selected"

			bpy.ops.mcprep.meshswap_spawner(block='Collection/fire', make_real=False)
			if 'fire' not in bpy.data.collections:
				return "Fire not in collections"
			count_torch = sum([1 for itm in bpy.data.collections if 'fire' in itm.name])
			if count_torch != 1:
				return "Imported extra fire group, should have cached instead!"

			# test that added item ends up in location location=(1,2,3)
			loc = (1,2,3)
			bpy.ops.mcprep.meshswap_spawner(block='Collection/fire', make_real=False, location=loc)
			if not bpy.context.object:
				return "Added meshswap object not added as active"
			elif not bpy.context.selected_objects:
				return "Added meshswap object not selected"
			if bpy.context.object.location != Vector(loc):
				return "Location not properly applied"
		else:
			# Add with make real = False
			bpy.ops.mcprep.meshswap_spawner(block='Group/banner', make_real=False)

			# test doing two of the same one (first won't be cached, second will)
			# Add one with make real = True
			bpy.ops.mcprep.meshswap_spawner(block='Group/fire', make_real=True)
			if 'fire' not in bpy.data.groups:
				return "Fire not in groups"
			elif not bpy.context.selected_objects:
				return "Added made-real meshswap objects not selected"

			bpy.ops.mcprep.meshswap_spawner(block='Group/fire', make_real=False)
			if 'fire' not in bpy.data.groups:
				return "Fire not in groups"
			count_torch = sum([1 for itm in bpy.data.groups if 'fire' in itm.name])
			if count_torch != 1:
				return "Imported extra fire group, should have cached instead!"

			# test that added item ends up in location location=(1,2,3)
			loc = (1,2,3)
			bpy.ops.mcprep.meshswap_spawner(block='Group/fire', make_real=False, location=loc)
			if not bpy.context.object:
				return "Added meshswap object not added as active"
			elif not bpy.context.selected_objects:
				return "Added meshswap object not selected"
			if bpy.context.object.location != Vector(loc):
				return "Location not properly applied"

	def meshswap_jmc2obj(self):
		"""Tests jmc2obj meshswapping"""
		self._clear_scene()
		self._import_jmc2obj_full()
		self._set_exporter('jmc2obj')

		# known jmc2obj material names which we expect to be able to meshswap
		test_materials = [
			"torch",
			"fire",
			"lantern",
			"cactus_side",
			"vines", # plural
			"enchant_table_top",
			"redstone_torch_on",
			"glowstone",
			"redstone_lamp_on",
			"pumpkin_front_lit",
			"sugarcane",
			"chest",
			"largechest",
			"sunflower_bottom",
			"sapling_birch",
			"white_tulip",
			"sapling_oak",
			"sapling_acacia",
			"sapling_jungle",
			"blue_orchid",
			"allium",
		]

		errors = []
		for mat_name in test_materials:
			try:
				res = self.meshswap_util(mat_name)
			except Exception as err:
				err = str(err)
				if len(err)>15:
					res = err[:15].replace("\n", "")
				else:
					res = err
			if res:
				errors.append(mat_name+":"+res)
		if errors:
			return "Meshswap failed: "+", ".join(errors)

	def meshswap_mineways_separated(self):
		"""Tests jmc2obj meshswapping"""
		self._clear_scene()
		self._import_mineways_separated()
		self._set_exporter('Mineways')

		# known Mineways (separated) material names expected for meshswap
		test_materials = [
			"grass",
			"torch",
			"fire_0",
			"MWO_chest_top",
			"MWO_double_chest_top_left",
			# "lantern", not in test object
			"cactus_side",
			"vine", # singular
			"enchanting_table_top",
			# "redstone_torch_on", no separate "on" for Mineways separated exports
			"glowstone",
			"redstone_torch",
			"jack_o_lantern",
			"sugar_cane",
			"jungle_sapling",
			"dark_oak_sapling",
			"oak_sapling",
			"campfire_log",
			"white_tulip",
			"blue_orchid",
			"allium",
		]

		errors = []
		for mat_name in test_materials:
			try:
				res = self.meshswap_util(mat_name)
			except Exception as err:
				err = str(err)
				if len(err)>15:
					res = err[:15].replace("\n", "")
				else:
					res = err
			if res:
				errors.append(mat_name+":"+res)
		if errors:
			return "Meshswap failed: "+", ".join(errors)

	def meshswap_mineways_combined(self):
		"""Tests jmc2obj meshswapping"""
		self._clear_scene()
		self._import_mineways_combined()
		self._set_exporter('Mineways')

		# known Mineways (separated) material names expected for meshswap
		test_materials = [
			"Sunflower",
			"Torch",
			"Redstone_Torch_(active)",
			"Lantern",
			"Dark_Oak_Sapling",
			"Sapling", # should map to oak sapling
			"Birch_Sapling",
			"Cactus",
			"White_Tulip",
			"Vines",
			"Ladder",
			"Enchanting_Table",
			"Campfire",
			"Jungle_Sapling",
			"Red_Tulip",
			"Blue_Orchid",
			"Allium",
		]

		errors = []
		for mat_name in test_materials:
			try:
				res = self.meshswap_util(mat_name)
			except Exception as err:
				err = str(err)
				if len(err)>15:
					res = err[:15].replace("\n", "")
				else:
					res = err
			if res:
				errors.append(mat_name+":"+res)
		if errors:
			return "Meshswap combined failed: "+", ".join(errors)

	def detect_desaturated_images(self):
		"""Checks the desaturate images function works"""
		# self._clear_scene() # not actually needed for this one

		from MCprep.materials.generate import is_image_grayscale
		base = self.get_mcprep_path()
		print("Raw base", base)
		base = os.path.join(base, "MCprep_resources",
			"resourcepacks", "mcprep_default", "assets", "minecraft", "textures",
			"block")
		print("Remapped base: ", base)

		# known images that ARE desaturated:
		desaturated = [
			"grass_block_top.png"
		]
		saturated = [
			"grass_block_side.png",
			"glowstone.png"
		]

		for tex in saturated:
			img = bpy.data.images.load(os.path.join(base, tex))
			if is_image_grayscale(img) is True:
				raise Exception('Image {} detected as grayscale, should be saturated'.format(tex))
		for tex in desaturated:
			img = bpy.data.images.load(os.path.join(base, tex))
			if is_image_grayscale(img) is False:
				raise Exception('Image {} detected as saturated - should be grayscale'.format(tex))

		# test that it is caching as expected.. by setting a false
		# value for cache flag and seeing it's returning the property value

	def qa_meshswap_file(self):
		"""Open the meshswap file, assert there are no relative paths"""
		blendfile = os.path.join("MCprep_addon", "MCprep_resources", "mcprep_meshSwap.blend")
		basepath = os.path.join("MCprep_addon", "MCprep_resources")
		basepath = os.path.abspath(basepath) # relative to the dev git folder
		bpy.ops.wm.open_mainfile(filepath=blendfile)
		# do NOT save this file!

		# bpy.ops.file.make_paths_relative() instead of this, do manually
		different_base = []
		not_relative = []
		for img in bpy.data.images:
			if not img.filepath:
				continue
			abspath = os.path.abspath(bpy.path.abspath(img.filepath))
			if not abspath.startswith(basepath):
				different_base.append(os.path.basename(img.filepath))
			if img.filepath != bpy.path.relpath(img.filepath):
				not_relative.append(os.path.basename(img.filepath))

		if len(different_base) > 50:
			return "Wrong basepath for image filepath comparison!"
		if different_base:
			return "Found {} images with different basepath from the meshswap file: {}".format(
				len(different_base), ", ".join(different_base))
		if not_relative:
			return "Found {} non relative img files in meshswap: {}".format(
				len(not_relative), ", ".join(not_relative))

		# detect any non canonical material names?? how to exclude?

		# Affirm that no materials have a principled node, should be basic only

	def item_spawner(self):
		"""Test item spawning and reloading"""
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props

		pre_items = len(scn_props.item_list)
		bpy.ops.mcprep.reload_items()
		post_items = len(scn_props.item_list)

		if pre_items != 0:
			return "Should have opened new file with unloaded assets?"
		elif post_items == 0:
			return "No items loaded"
		elif post_items < 50:
			return "Too few items loaded, missing texturepack?"

		# spawn with whatever default index
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.spawn_item()
		post_objs = len(bpy.data.objects)

		if post_objs == pre_objs:
			return "No items spawned"
		elif post_objs > pre_objs+1:
			return "More than one item spawned"

		# test core useage on a couple of out of the box textures

		# test once with custom block
		# bpy.ops.mcprep.spawn_item_file(filepath=)

		# test with different thicknesses

		# test after changing resource pack

		# test that with an image of more than 1k pixels, it's truncated as expected

		# test with different

	def world_tools(self):
		"""Test adding skies, prepping the world, etc"""
		from MCprep.world_tools import get_time_object

		# test with both engines (cycles+eevee, or cycles+internal)
		self._clear_scene()
		bpy.ops.mcprep.world()

		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_shader',
			# initial_time='8',
			add_clouds=True,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# find the sun, ensure it's pointed partially to the side
		obj = get_time_object()
		if not obj:
			return "No detected MCprepHour controller (a)"

		self._clear_scene()
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_mesh',
			# initial_time='12',
			add_clouds=False,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# find the sun, ensure it's pointed straight down
		obj = get_time_object()
		if not obj:
			return "No detected MCprepHour controller (b)"

		self._clear_scene()
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_only',
			# initial_time='18',
			add_clouds=False,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# find the sun, ensure it's pointed straight down
		obj = get_time_object()
		if not obj:
			return "No detected MCprepHour controller (c)"

		self._clear_scene()
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_static_mesh',
			# initial_time='0',
			add_clouds=False,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# find the sun, ensure it's pointed straight down
		obj = get_time_object()
		if obj:
			return "Found MCprepHour controller, shouldn't be one (d)"

		self._clear_scene()
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_static_only',
			# initial_time='6',
			add_clouds=False,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# find the sun, ensure it's pointed straight down
		obj = get_time_object()
		if obj:
			return "Found MCprepHour controller, shouldn't be one (e)"

		# test that it removes existing suns by first placing one, and then
		# affirming it's gone


class OCOL:
	"""override class for colors, for terminals not supporting color-out"""
	HEADER = ''
	OKBLUE = ''
	OKGREEN = ''
	WARNING = '[WARN]'
	FAIL = '[ERR]'
	ENDC = ''
	BOLD = ''
	UNDERLINE = ''


class COL:
	"""native_colors to use, if terminal supports color out"""
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'


def suffix_chars(string, max_char):
	"""Returns passed string or the last max_char characters if longer"""
	string = string.replace('\n', '\\n ')
	string = string.replace(',', ' ')
	if len(string)>max_char:
		return string[-max_char:]
	return string

# -----------------------------------------------------------------------------
# Testing file, to semi-auto check addon functionality is working
# Run this as a script, which creates a temp MCprep - test panel
# and cycle through all tests.
# -----------------------------------------------------------------------------


class MCPTEST_OT_test_run(bpy.types.Operator):
	bl_label = "MCprep run test"
	bl_idname = "mcpreptest.run_test"
	bl_description = "Run specified test index"

	index = bpy.props.IntProperty(default=0)

	def execute(self, context):
		# ind = context.window_manager.mcprep_test_index
		test_class.mcrprep_run_test(self.index)
		return {'FINISHED'}


class MCPTEST_OT_test_selfdestruct(bpy.types.Operator):
	bl_label = "MCprep test self-destruct (dereg)"
	bl_idname = "mcpreptest.self_destruct"
	bl_description = "Deregister the MCprep test script, panel, and operators"

	def execute(self, context):
		print("De-registering MCprep test")
		unregister()
		return{'FINISHED'}


class MCPTEST_PT_test_panel(bpy.types.Panel):
	"""MCprep test panel"""
	bl_label = "MCprep Test Panel"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS' if bpy.app.version < (2,80) else 'UI'
	bl_category = "MCprep"

	def draw_header(self, context):
		col = self.layout.column()
		col.label("",icon="ERROR")

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.label(text="Select test case:")
		col.prop(context.window_manager, "mcprep_test_index")
		col.operator("mcpreptest.run_test").index = context.window_manager.mcprep_test_index
		col.prop(context.window_manager, "mcprep_test_autorun")
		col.label(text="")

		r = col.row()
		subc = r.column()
		subc.scale_y = 0.8
		# draw test results thus far:
		for i, itm in enumerate(test_class.test_cases):
			row = subc.row(align=True)

			if test_class.test_cases[i][1]["check"]==1:
				icn = "COLOR_GREEN"
			elif test_class.test_cases[i][1]["check"]==-1:
				icn = "COLOR_GREEN"
			elif test_class.test_cases[i][1]["check"]==-2:
				icn = "QUESTION"
			else:
				icn = "MESH_CIRCLE"
			row.operator("mcpreptest.run_test", icon=icn, text="").index=i
			row.label("{}-{} | {}".format(
				test_class.test_cases[i][1]["type"],
				test_class.test_cases[i][0],
				test_class.test_cases[i][1]["res"]
				)
			)
		col.label(text="")
		col.operator("mcpreptest.self_destruct")

def mcprep_test_index_update(self, context):
	if context.window_manager.mcprep_test_autorun:
		print("Auto-run MCprep test")
		bpy.ops.mcpreptest.run_test(index=self.mcprep_test_index)


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	MCPTEST_OT_test_run,
	MCPTEST_OT_test_selfdestruct,
	MCPTEST_PT_test_panel
)


def register():
	print("REGISTER MCPREP TEST")
	maxlen = len(test_class.test_cases)

	bpy.types.WindowManager.mcprep_test_index = bpy.props.IntProperty(
		name="MCprep test index",
		default=-1,
		min=-1,
		max=maxlen,
		update=mcprep_test_index_update)
	bpy.types.WindowManager.mcprep_test_autorun = bpy.props.BoolProperty(
		name="Autorun test",
		default=True
		)

	# context.window_manager.mcprep_test_index = -1 put into handler to reset?
	for cls in classes:
		# util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	print("DEREGISTER MCPREP TEST")
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	del bpy.types.WindowManager.mcprep_test_index
	del bpy.types.WindowManager.mcprep_test_autorun


if __name__ == "__main__":
	global test_class
	test_class = mcprep_testing()

	register()

	# setup paths to the target
	test_class.setup_env_paths()

	# check for additional args, e.g. if running from console beyond blender
	if "--" in sys.argv:
		argind = sys.argv.index("--")
		args = sys.argv[argind + 1:]
	else:
		args = []

	if "-v" in args:
		test_class.suppress = False
	else:
		test_class.suppress = True

	if "-run" in args:
		ind = args.index("-run")
		if len(args) > ind:
			test_class.run_only = args[ind+1]

	if "--auto_run" in args:
		test_class.run_all_tests()

