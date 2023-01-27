import os
import hou
import re

class BuildMtlxNetwork():
    def __init__(self):
        self.mtlx_input_names = None
        self.shader_node_names = []
        self.textures_folder = os.path.abspath(hou.node(hou.pwd().path()).evalParm("texture_folder"))
        self.FBX_path_node = hou.node(hou.node(hou.pwd().path()).evalParm("fbx_subnet"))
        self.fbx_geos = self.FBX_path_node.recursiveGlob("*", hou.nodeTypeFilter.ObjGeometry) # IF TYPE GEOMETRY
        self.fbx_geos_shader_names = {}

        # Naming convention
        self.baseColor_list = ["base","diffuse","albedo","diff"]
        self.metallic_list = ["metallic","metalness"]
        self.specular_list = ["specular","spec"]
        self.roughness_list = ["roughness","rough","gloss","glossiness"]
        self.normal_list = ["normal","nrm"]


        # Creation
        if not hou.node(hou.pwd().path() + "/lopnet"):  
            self.Lopnet_network = hou.pwd().createNode("lopnet", "lopnet")
            self.matlib_node = self.Lopnet_network.createNode("materiallibrary", "matlib")
            self.geometries_subnet = self.matlib_node.createInputNode(0, "subnet", "geometries")
            self.usd_rop = self.Lopnet_network.createNode("usd_rop", "Export_USD")
            self.sublayer = self.Lopnet_network.createNode("sublayer", "Import_USD")

            self.usd_rop.setParms({"lopoutput": "$HIP/geo/OS.usd", "savestyle":"flattenstage"})
            self.sublayer.setParms({"filepath1": '`chs("../Export_USD/lopoutput")`'})
            
            self.usd_rop.setInput(0,self.matlib_node)
        else:
            self.Lopnet_network = hou.node(hou.pwd().path() + "/lopnet")
            self.matlib_node = hou.node(hou.pwd().path() + "/matlib")
            self.geometries_subnet = hou.node(hou.pwd() + "/geometries")
            self.usd_rop = hou.node(hou.pwd() + "/Export_USD")
            self.sublayer = hou.node(hou.pwd() + "/Import_USD")
        self.Lopnet_network.layoutChildren()
                   
    def copyTransforms(self, a, b):
        b.setParms({"tx": a.evalParm("tx"), "ty": a.evalParm("ty"), "tz": a.evalParm("tz"),
                    "rx": a.evalParm("rx"), "ry": a.evalParm("ry"), "rz": a.evalParm("rz"),    
                    "sx": a.evalParm("sx"), "sy": a.evalParm("sy"), "sz": a.evalParm("sz"),
                    "scale": a.evalParm("scale"),    
                    "px": a.evalParm("px"), "py": a.evalParm("py"), "pz": a.evalParm("pz"),
                    "prx": a.evalParm("prx"), "pry": a.evalParm("pry"), "prz": a.evalParm("prz"),            
        })

    def getInfoAboutFBX(self):
        for i, fbx_nodes in enumerate(self.fbx_geos):
            for shop in fbx_nodes.displayNode().geometry().findPrimAttrib("shop_materialpath").strings():
                result = re.search(r"(\w*$)", shop) # get FBX Principled shader's name
                if result.group(1) == "":
                    pass
                else:
                    self.fbx_geos_shader_names[result.group(1)] = [] # Create dictionary of all FBX shaders.

    def getFilesInFolder(self):
        texture_paths = []
        textures_name = [f for f in os.listdir(self.textures_folder) if os.path.isfile(os.path.join(self.textures_folder, f))]
        
        for x, name in enumerate(self.fbx_geos_shader_names.keys()):
            temp_texture_names = [] # Temporary list to be append into list after loop
            for y,texture_name in enumerate(textures_name):
                if(texture_name.lower().find(str(name.lower())) >= 0): # If shader name (from shop_materialpath) matches the Image file naming = append to list
                    temp_texture_names.append(texture_name) 
                else:
                    pass
            self.fbx_geos_shader_names[name] = temp_texture_names # feed list into corresponding values

    def createReferenceGeometries(self):
        merge_node = hou.node(self.geometries_subnet.path() + "/output0").createInputNode(0, "merge","merge")
        for i, node in enumerate(self.fbx_geos):
            fbx_sop = hou.node(self.FBX_path_node.path() + "/" + str(self.fbx_geos[i]))
            transform_node = self.geometries_subnet.createNode("xform", str(self.fbx_geos[i]) + "_transform")
            reference_geo = transform_node.createInputNode(0, "sopimport", str(self.fbx_geos[i]))
            reference_geo.setParms({"soppath": fbx_sop.path(),
            "pathprefix": "/Geometries/$OS",
            "bindmaterials":"createbind",
            "enable_partitionattribs":1,
            "enable_prefixpartitionsubsets":1,
            "prefixpartitionsubsets":0,
            "partitionattribs":"materialBind",
            })

            merge_node.setNextInput(transform_node)
            self.copyTransforms(fbx_sop, transform_node) # Copy transforms from FBX Nodes
        self.geometries_subnet.layoutChildren()

    def modifyFBX(self):
        for i, node in enumerate(self.fbx_geos):
            # find "file" node inside geo
            file_node = node.cookPathNodes()[-1]

            #create "output" primwrangle with vex inside
            snippet_code = '''// Create "usdmaterialpath" and "materialBind" for subsets
s@materialBind = re_replace(r"(.*\/)", "", @shop_materialpath);
s@shop_materialpath = sprintf("/materials/%s", s@materialBind);
s@usdmaterialpath = s@shop_materialpath;      
'''
            primwrangle_node = node.createNode("attribwrangle","output")
            primwrangle_node.setParms({"class":"primitive"})
            primwrangle_node.parm("snippet").set(snippet_code)
            primwrangle_node.setInput(0,file_node)
            primwrangle_node.setDisplayFlag("on")
            primwrangle_node.setRenderFlag("on")
            node.layoutChildren()

    def createShaderSubnets(self):
        # Create reference "mtlxstandard_surface" node
        if not hou.node("{0}/reference_mtlx".format(self.matlib_node.path())):
            mtlx_ref = self.matlib_node.createNode("mtlxstandard_surface", "reference_mtlx")
        else:
            mtlx_ref = hou.node("{0}/reference_mtlx".format(self.matlib_node.path()))
        
        # Get all input names from MTLX REFERENCE
        self.mtlx_input_names = mtlx_ref.inputNames()
        mtlx_ref.destroy()
        
        # Create subnets with initial nodes
        for key, value in self.fbx_geos_shader_names.items():
            if not hou.node("{0}/{1}".format(self.matlib_node.path(), key)):
                current_subnet = self.matlib_node.createNode("subnet", key)
                current_subnet.setMaterialFlag("on")
                current_subnet.deleteItems(current_subnet.allItems())
            else:
                pass
        self.matlib_node.layoutChildren()
        self.matlib_node.setParms({"assign1": 1})

    def createMtlxImage(self, filename, filename_stripped, string_list, selected_node, in_num, signature):
        for item in string_list:
            if(filename_stripped.lower().find(str(item.lower())) >= 0):
                current_img = selected_node.createInputNode(in_num, "mtlximage", selected_node.inputNames()[in_num])
                current_img.setParms({"file": self.textures_folder + "\\" + filename,"signature":signature})
                current_img.setInput(1, self.mtlxuv, 0)
                # print("Found:", item)
                break
            else:
                pass
    
    def setupEachShader(self):
        for texture, value in self.fbx_geos_shader_names.items():
            # debug print
            # print("\n")
            # print("Processing: ", texture)

            hou.ui.setStatusMessage("Setting up Shader Subnets -> " + texture)
            # Get current subnet
            current_subnet = hou.node("{0}/{1}".format(self.matlib_node.path(), texture))
            if not current_subnet.allItems():            
                # Surface output
                
                output_surface = current_subnet.createNode("subnetconnector", "surface_output")
                output_surface.setParms({"connectorkind": 1, "parmname": "surface", "parmlabel": "Surface", "parmtype": "surface"})
                
                # Displacement output
                output_displacement = current_subnet.createNode("subnetconnector", "displacement_output")
                output_displacement.setParms({"connectorkind": 1, "parmname": "displacement", "parmlabel": "Displacement", "parmtype": "displacement"})
                
                # connect nodes
                displacement_node = output_displacement.createInputNode(0, "mtlxdisplacement", "mtlxdisplacement")
                displacement_node.setParms({"scale": 0.01})
                self.mtlx_node = output_surface.createInputNode(0, "mtlxstandard_surface", "mtlx_material")
                self.mtlxuv = current_subnet.createNode("mtlxtexcoord", "mtlxtexcoord")
                self.mtlxuv.setParms({"signature": "vector2"})
                
                # Create and connect images
                for i, filename in enumerate(self.fbx_geos_shader_names[texture]):
                    # debug print
                    # print("Found: ", filename)
                    
                    # get rid of shader in the string
                    filename_stripped = filename.replace(texture,"")

                    # compare inside if statement                    
                    self.createMtlxImage(filename, filename_stripped, self.baseColor_list, self.mtlx_node, 1, "color3")
                    self.createMtlxImage(filename, filename_stripped, self.roughness_list, self.mtlx_node, 6, "float")
                    self.createMtlxImage(filename, filename_stripped, self.specular_list, self.mtlx_node, 5, "color3")
                    self.createMtlxImage(filename, filename_stripped, self.metallic_list, self.mtlx_node, 3, "float")
                    self.createMtlxImage(filename, filename_stripped, self.normal_list, displacement_node, 0, "vector3")

                current_subnet.layoutChildren()
        self.matlib_node.parm("fillmaterials").pressButton()
            
def execute_conversion():
    if hou.node(hou.pwd().path() + "/lopnet"): 
        hou.node(hou.pwd().path() + "/lopnet").destroy()
    bmn = BuildMtlxNetwork()
    bmn.getInfoAboutFBX()
    bmn.modifyFBX()
    bmn.getFilesInFolder()
    bmn.createReferenceGeometries()
    bmn.createShaderSubnets()
    bmn.setupEachShader()
    hou.ui.displayConfirmation("Lopnet Finished!")
    hou.ui.setStatusMessage("Lopnet Finished!")
