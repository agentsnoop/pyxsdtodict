from six import iteritems
import os

import pyxmltodict

NAMESPACES = {
	"http://www.vmware.com/schema/ovf": "vmw",
	"http://www.vmware.com/vcloud/extension/v1.5": "vmext",
	"http://www.vmware.com/vcloud/v1.5": "vcloud",
	"http://www.vmware.com/vcloud/versions": "versions",
	"http://www.vmware.com/schema/ovfenv": "ve",
	"http://schemas.dmtf.org/ovf/envelope/1": "ovf",
	"http://schemas.dmtf.org/ovf/environment/1": "ovfenv",
	"http://schemas.dmtf.org/wbem/wscim/1/common": "cim",
	"http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData": "rasd",
	"http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData": "vssd",
}

MEMBER_REDIRECT = {
	"type": "type_",
	"id": "id_",
	"class": "class_",
	"object": "object_",
	"format": "format_",
	"EntityType": "EntityType_"
}

TYPE_REDIRECT = {
	"xs:boolean": "bool",
	"xs:string": "str",
	"xs:long": "long",
	"xs:int": "int",
	"xs:short": "int",
	"xs:byte": "byte",
	"xs:double": "float",
	"xs:float": "float",
	"xs:unsignedLong": "long",
	"xs:unsignedInt": "int",
	"xs:unsignedShort": "int",
	"xs:unsignedByte": "byte",
	"xs:hexBinary": "int",
	"xs:base64Binary": "long",
	"xs:anyURI": "str",
	"xs:anyType": "str",
	"xs:dateTime": "str",
	"xs:anySimpleType": "str",
	"xml:lang": "str",
	"anyAttribute": "dict",
}

def parse_path(path):
	namespaces 	= {}
	members 	= {}
	fs, ds, xfs, xds = _get_files(path, exts="xsd")
	for f in sorted(fs):
		subdata = pyxmltodict.parse_path(f)
		data, namespace, members = _parse_xsd(subdata, namespaces, members)
		namespace = NAMESPACES[namespace]
		if namespace not in namespaces:
			namespaces[namespace] = {}
		namespaces[namespace].update(data)
	return namespaces

def convert_path(src, dst):
	types = parse_path(src)

	ns_dst_template = "{base}/{{namespace}}".format(base=dst)
	total = 0
	for namespace, subtypes in iteritems(types):
		total += len(subtypes)
		for type_name in subtypes:
			print "writing: {namespace}:{type_name}".format(namespace=namespace, type_name=type_name)
			ns_dst = ns_dst_template.format(namespace=namespace)
			if not os.path.exists(ns_dst):
				os.makedirs(ns_dst)
				with open("{dst}/__init__.py".format(dst=ns_dst), "w+") as fd:
					pass
	_write_mappings_condensed(types, dst)

	print "Wrote {num} files".format(num=total)

def _write_mappings(types, dst):
	with open("{dst}/mapping.py".format(dst=dst), "w+") as fd:
		fd.write("MAPPINGS = {\n")
		for ns, subtypes in iteritems(types):
			fd.write("\t'{namespace}': {{\n".format(namespace=ns))
			for name, subtype in iteritems(subtypes):
				members 		= subtype.get("members")
				content_type 	= subtype.get("content_type")
				name 			= subtype.get("name")
				namespace 		= subtype.get("namespace")
				parent 			= subtype.get("parent")
				abstract		= subtype.get("abstract")

				fd.write("\t\t'{name}': {{\n".format(name=name))
				fd.write("\t\t\t'content_type': {value},\n".format(value="'"+content_type+"'" if content_type else "None"))
				fd.write("\t\t\t'members': [\n")
				fd.write("\t\t\t\t# name, namespace, parent, required, is_list\n")
				for m in members:
					m_type = None
					if m[2]:
						m_type = m[2].split(":")[-1]
					m += (types.get(m[1], {}).get(m_type, {}).get("abstract", False),)
					fd.write("\t\t\t\t{value},\n".format(value=str(m)))
				fd.write("\t\t\t],\n")
				fd.write("\t\t\t'name': {value},\n".format(value="'"+name+"'" if name else "None"))
				fd.write("\t\t\t'namespace': {value},\n".format(value="'"+namespace+"'" if namespace else "None"))
				fd.write("\t\t\t'parent': {value},\n".format(value="'"+parent+"'" if parent else "None"))
				fd.write("\t\t\t'abstract': {value},\n".format(value=abstract == 'true'))
				fd.write("\t\t},\n")
			fd.write("\t},\n")
		fd.write("}\n")

def _write_mappings_condensed(types, dst):
	with open("{dst}/mapping.py".format(dst=dst), "w+") as fd:
		fd.write("MAPPINGS = {\n")
		fd.write("\t'vcd': {\n")
		for ns, subtypes in iteritems(types):
			fd.write("\t\t'{namespace}': {{\n".format(namespace=ns))
			for name, subtype in iteritems(subtypes):
				members = subtype.get("members")
				content_type = subtype.get("content_type")
				name = subtype.get("name")
				namespace = subtype.get("namespace")
				parent = subtype.get("parent")
				abstract = subtype.get("abstract")
				fd.write("\t\t\t'{name}': [".format(name=name))
				fd.write("{value}, ".format(value="'"+namespace+"'" if namespace else "None"))
				fd.write("{value}, ".format(value="'"+parent+"'" if parent else "None"))
				fd.write("{value}, ".format(value=abstract == True or abstract == "true"))
				fd.write("{value}, ".format(value="'"+content_type+"'" if content_type else "None"))
				fd.write("[")
				for m in members:
					m_type = None
					if m[2]:
						m_type = m[2].split(":")[-1]
					m += (types.get(m[1], {}).get(m_type, {}).get("abstract", False), )
					fd.write("{value}, ".format(value=str(m)))
				fd.write("], ")
				fd.write("],\n")
			fd.write("\t\t},\n")
		fd.write("\t}\n")
		fd.write("}\n")

def _parse_xsd(data, namespaces, members):
	types 		= {}
	defer		= []
	schema		= data.get("schema", {})
	namespace 	= schema.get("targetNamespace")
	attributes	= _get_items(schema, "attribute")
	elements	= _get_items(schema, "element")
	for m in attributes + elements:
		members[m.get("name")] = m

	simple_types = schema.get("simpleType", [])
	if not isinstance(simple_types, list):
		simple_types = [simple_types]
	for s in simple_types:
		types[s.get("name")] = _get_data_from_simple_type(s, namespace, namespaces, types, members, defer)

	complex_types = schema.get("complexType", [])
	if not isinstance(complex_types, list):
		complex_types = [complex_types]
	for c in complex_types:
		complex_type = _get_data_from_complex_type(c, namespace, namespaces, types, members, defer)
		if complex_type:
			types[c.get("name")] = complex_type

	if defer:
		diff = len(defer)
		failed = []
		while diff > 0:
			for c in defer:
				complex_type = _get_data_from_complex_type(c, namespace, namespaces, types, members, failed)
				if complex_type:
					types[c.get("name")] = complex_type
			diff 	= len(defer) - len(failed)
			defer 	= failed
			failed 	= []

		if failed:
			print "Failed types"
			for f in failed:
				print "   ", f.get("name", f.get("ref"))

	return types, namespace, members

def replace_end(word, search, replacement):
	return word[::-1].replace(search[::-1], replacement[::-1], 1)[::-1]
	
def _get_files(path, max_depth=None, exts=None, exclude_exts=None, exclude_dirs=None, forbidden_dirs=None, base_path=None, visited=None, exclude_hidden=False):
	"""
	Gets all files recursively starting at a particular path

	:param string path: Path to start
	:param int max_depth: Max depth to traverse. None means no limit
	:param string/list exts: Extensions to acquire
	:param string/list exclude_exts: Extensions to exclude
	:param string/list exclude_dirs: Directories to exclude (relative)
	:param string/list forbidden_dirs: Directories to never enter (absolute)
	:param string base_path: Internal paramter to keep track of starting path
	:param list visited: List of paths already visited
	:param bool exclude_hidden: Whether or not hidden files or directories should be excluded
	:return: A list of file paths, excluded files, dirs, and excluded dirs
	:rtype: list, list, list, list
	"""
	if exts is None:
		exts = []
	elif not isinstance(exts, list):
		exts = [exts]

	if exclude_exts is None:
		exclude_exts = []
	elif not isinstance(exclude_exts, list):
		exclude_exts = [exclude_exts]

	if exclude_dirs is None:
		exclude_dirs = []
	elif not isinstance(exclude_dirs, list):
		exclude_dirs = [exclude_dirs]

	if forbidden_dirs is None:
		forbidden_dirs = []

	if base_path is None:
		base_path = path

	if visited is None:
		visited = []

	files 			= []
	excluded_files 	= []
	dirs			= []
	excluded_dirs	= []

	if (max_depth is not None and max_depth < 1) or not os.path.exists(path):
		return files, excluded_files, dirs, excluded_dirs

	exclude_dirs = [os.path.realpath(d) if d.startswith("/") else os.path.realpath(os.path.join(base_path, d)) for d in exclude_dirs]
	if path not in exclude_dirs and not any([path.startswith(d) for d in forbidden_dirs]):
		dirs.append(path)
		for f in os.listdir(path):
			try:
				file_path = os.path.realpath(os.path.join(path, f))
			except Exception:
				continue
			if file_path is None or file_path in visited:
				continue
			visited.append(file_path)
			ext = None
			if exclude_hidden and f.startswith("."):
				excluded_files.append(file_path)
				continue
			if f.startswith("."):
				f = f.lstrip(".")
			if "." in f:
				ext = f.split(".")[-1]
			if os.path.isfile(file_path):
				if (exts == [] and ext not in exclude_exts) or (ext is not None and ext in exts):
					files.append(file_path)
					continue
				excluded_files.append(file_path)
			elif os.path.isdir(file_path):
				args = [file_path, max_depth-1 if max_depth is not None else None, exts, exclude_exts, exclude_dirs, forbidden_dirs, base_path, visited, exclude_hidden]
				new_files, new_excluded_files, new_dirs, new_excluded_dirs = _get_files(*args)
				dirs			+= new_dirs
				files 			+= new_files
				excluded_files 	+= new_excluded_files
				excluded_dirs	+= new_excluded_dirs
	else:
		excluded_dirs.append(path)
	return files, excluded_files, dirs, excluded_dirs
def _get_data_from_simple_type(s, namespace, namespaces, types, schema_members, defer):
	name = s.get("name")
	print "Processing {namespace}:{name}".format(namespace=NAMESPACES.get(namespace), name=name)
	subdata = {
		"name": name,
		"namespace": namespace,
		"content_type": "",
		"parent": s.get("restriction", {}).get("base"),
		"abstract": s.get("abstract", False),
		"members": []
	}
	return subdata

def _get_data_from_complex_type(c, namespace, namespaces, types, schema_members, defer):
	name = c.get("name")
	print "Processing {namespace}:{name}".format(namespace=NAMESPACES.get(namespace), name=name)
	members = []

	elements, attributes, complex_parent = _get_from_extension(c, "complexContent")
	members += elements+attributes

	elements, attributes, complex_parent_2 = _get_from_content(c, "complexContent")
	members += elements+attributes

	elements, attributes, simple_parent = _get_from_extension(c, "simpleContent")
	members += elements+attributes

	elements, attributes, simple_parent_2 = _get_from_content(c, "simpleContent")
	members += elements+attributes

	elements, attributes, simple_parent_3 = _get_from_type(c)
	members += elements+attributes

	parent = "BaseSchemaType"
	if complex_parent_2:
		complex_parent = complex_parent_2

	if simple_parent_3:
		simple_parent = simple_parent_3
	elif simple_parent_2:
		simple_parent = simple_parent_2

	if complex_parent == simple_parent:
		parent = complex_parent
	elif complex_parent == "BaseSchemaType":
		parent = simple_parent
	elif simple_parent == "BaseSchemaType":
		parent = complex_parent

	member_data = []
	for m in members:
		ref = m.get("ref")
		datum = None
		if m.get("name"):
			datum = _create_from_name(m, name, namespace, namespaces, types, schema_members, defer)
		elif ref:
			datum = _create_from_reference(m, ref, name, namespace, namespaces, types, schema_members, defer)

		if not datum:
			defer.append(c)
			return
		member_data.append(datum)

	appinfo = c.get("annotation", {}).get("appinfo", {})
	if not isinstance(appinfo, list):
		appinfo = [appinfo]
	content_type = ""
	for a in appinfo:
		content_type = a.get("content-type")
	subdata = {
		"name": name,
		"namespace": namespace,
		"content_type": content_type,
		"parent": parent,
		"abstract": c.get("abstract", False),
		"members": member_data
	}
	return subdata

def _create_from_name(m, type_name, namespace, namespaces, types, schema_members, defer):
	sub_complex_type = None
	complex_type = m.get("complexType")
	if complex_type:
		base = replace_end(replace_end(type_name, "_Type", ""), "Type", "")
		complex_type["name"] = "{base}{name}Type".format(base=base, name=m.get("name"))
		sub_complex_type = _get_data_from_complex_type(complex_type, namespace, namespaces, types, schema_members, defer)
		if sub_complex_type:
			# print "   ", "creating subtype for", complex_type.get("name")
			types[complex_type.get("name")] = sub_complex_type

	return (
		MEMBER_REDIRECT.get(m.get("name"), m.get("name")),  						# Modified name
		NAMESPACES.get(namespace, namespace),  										# Namespace
		sub_complex_type.get("name") if sub_complex_type else m.get("type"),  		# Type
		m.get("minOccurs", "0") != "0" or m.get("required") is not None,  			# Required or not
		m.get("maxOccurs", "1") != "1")  											# List or not

def _create_from_reference(m, ref, type_name, namespace, namespaces, types, schema_members, defer):
	ref_name 	= ref
	ref_ns 		= namespace
	if ":" in ref_name:
		ref_ns		= ref_name.split(":")[0]
		ref_name 	= ref_name.split(":")[1]

	type_name_1 = type_name_2 = ref_name
	if not ref_name.endswith("Type"):
		type_name_1 = "{name}Type".format(name=ref_name)
		type_name_2	= "{name}_Type".format(name=ref_name)

	type_ = None
	if ref_ns != namespace:
		type_ = namespaces.get(ref_ns, {}).get(type_name_1, namespaces.get(ref_ns, {}).get(type_name_2))
	else:
		type_ = types.get(type_name_1, types.get(type_name_2))

	if type_:
		return (
			MEMBER_REDIRECT.get(ref_name, ref_name), 	 							# Modified name
			NAMESPACES.get(ref_ns, ref_ns),											# Namespace
			type_.get("name"),  													# Type
			m.get("minOccurs", "0") != "0" or m.get("required") is not None,  		# Required or not
			m.get("maxOccurs", "1") != "1")  										# List or not
	else:
		m_ref = schema_members.get(ref_name)
		if not m_ref:
			if TYPE_REDIRECT.get(ref):
				m_ref = {"name": ref_name, "type": ref}
		if m_ref:
			if m_ref.get("type"):
				return (
					MEMBER_REDIRECT.get(ref_name, ref_name),  							# Modified name
					NAMESPACES.get(ref_ns, ref_ns),										# Namespace
					m_ref.get("type"),  												# Type
					m.get("minOccurs", "0") != "0" or m.get("required") is not None,  	# Required or not
					m.get("maxOccurs", "1") != "1")  									# List or not
			else:
				complex_type = m_ref.get("complexType")
				base = replace_end(replace_end(m_ref.get("name"), "_Type", ""), "Type", "")
				# print "...creating for reference: {base}, {name}".format(base=base, name=m_ref.get("name"))
				complex_type["name"] = m_ref.get("name") 	# "{base}Type".format(base=base)
				sub_complex_type = _get_data_from_complex_type(complex_type, namespace, namespaces, types, schema_members, defer)
				if sub_complex_type:
					# print "   ", "creating subtype for", complex_type.get("name")
					types[sub_complex_type.get("name")] = sub_complex_type
				return (
					MEMBER_REDIRECT.get(m_ref.get("name"), m_ref.get("name")),  					# Modified name
					NAMESPACES.get(ref_ns, ref_ns),													# Namespace
					sub_complex_type.get("parent") if sub_complex_type else m_ref.get("type"),  	# Type
					m_ref.get("minOccurs", "0") != "0" or m_ref.get("required") is not None,  		# Required or not
					m_ref.get("maxOccurs", "1") != "1")												# List or not
		else:
			print "    Deferring to create {ref} for {name}".format(ref=ref, name=type_name)

def _get_from_extension(container, content_type):
	extension 	= container.get(content_type, {}).get("extension", {})
	parent 		= extension.get("base", "BaseSchemaType")
	elements, attributes, __ = _get_from_type(extension)
	return elements, attributes, parent

def _get_from_content(container, content_type):
	content = container.get(content_type, {})
	return _get_from_type(content)

def _get_from_type(container):
	parent = container.get("restriction", {}).get("base")

	attributes	= _get_items(container, "attribute")
	# if "anyAttribute" in container:
	# 	attributes.append({"name": "_anyAttribute", "type": "dict"})
	elements	= _get_items(container, "element")

	sequences 	= _get_items(container, "sequence")
	choices		= _get_items(container, "choice")
	for c in choices:
		elements += _get_items(c, "element")
		sequences = _get_items(c, "sequence")

	for s in sequences:
		elements += _get_items(s, "element")
		choices = _get_items(s, "choice")
		for c in choices:
			elements += _get_items(c, "element")
			sub_sequences = _get_items(c, "sequence")
			for s_ in sub_sequences:
				elements += _get_items(s_, "element")
	return elements, attributes, parent

def _get_items(container, name):
	items = container.get(name, [])
	if not isinstance(items, list):
		items = [items]
	return items

def get_parent_members(type_name, types, namespace):
	members = []
	if namespace == "xs":
		return members

	data = types[namespace].get(type_name)
	if not data:
		return members

	parent = ""
	if isinstance(data, dict):
		parent = data.get("parent")
		members += data.get("members", [])
	elif isinstance(data, list):
		parent = data[1]
		members += data[4]

	if ":" in parent:
		name_parts 	= parent.split(":")
		namespace 	= name_parts[0]
		parent 		= name_parts[1]
	if parent != "object" and parent != "BaseSchemaType":
		members += get_parent_members(parent, types, namespace)
	return members

def parse_name(name, default_namespace):
	namespace = default_namespace
	if ":" in name:
		parts = name.split(":")
		name = parts[1]
		namespace = parts[0]
	return name, namespace
