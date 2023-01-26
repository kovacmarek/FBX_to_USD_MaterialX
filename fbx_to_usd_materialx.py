import os
import hou
import re

class BuildMtlxNetwork():
    def __init__(self):
        self.mtlx_input_names = None
        self.shader_node_names = []
        # self.textures_folder = os.path.abspath("C:\\SSD\\Marie\\files\\knight-artorias\\textures")
        self.textures_folder = os.path.abspath("C:\\SSD\\Marie\\files\\m1-garand\\textures")
        self.FBX_path_node = hou.node("/obj/Artorias_fbx_orig_test/")
        self.fbx_geos = self.FBX_path_node.recursiveGlob("*", hou.nodeTypeFilter.ObjGeometry)
        self.fbx_geos_shader_names = {}

        # Creation
        if not hou.node("/stage/lopnet"):  
            self.Lopnet_network = hou.node("/stage").createNode("lopnet", "lopnet")
            self.matlib_node = self.Lopnet_network.createNode("materiallibrary", "matlib")
            self.geometries_subnet = self.matlib_node.createInputNode(0, "subnet", "geometries")
        else:
            self.Lopnet_network = hou.node("/stage/lopnet")
            self.matlib_node = hou.node("/stage/lopnet/matlib")
            self.geometries_subnet = hou.node("/stage/lopnet/geometries")
                   
    def copyTransforms(self, a, b):
        b.setParms({"tx": a.evalParm("tx"), "ty": a.evalParm("ty"), "tz": a.evalParm("tz"),
                    "rx": a.evalParm("rx"), "ry": a.evalParm("ry"), "rz": a.evalParm("rz"),    
                    "sx": a.evalParm("sx"), "sy": a.evalParm("sy"), "sz": a.evalParm("sz"),
                    "scale": a.evalParm("scale"),    
                    "px": a.evalParm("px"), "py": a.evalParm("py"), "pz": a.evalParm("pz"),
                    "prx": a.evalParm("prx"), "pry": a.evalParm("pry"), "prz": a.evalParm("prz"),            
        })

    def getInfoAboutFBX(self):
        # print(self.fbx_geos[0].displayNode().geometry().findPrimAttrib("shop_materialpath").strings())
        for i, fbx_nodes in enumerate(self.fbx_geos):
            for shop in fbx_nodes.displayNode().geometry().findPrimAttrib("shop_materialpath").strings():
                result = re.search(r"(\w*$)", shop) # get FBX Principled shader's name
                if result.group(1) == "":
                    pass
                else:
                    self.fbx_geos_shader_names[result.group(1)] = [] # Create dictionary of all FBX shaders.

    def getFilesInFolder(self):
        texture_paths = []
        # TODO rework "textures_name" into dictionary with it's filename & absolute path

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
        print(self.fbx_geos[0])
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
        self.matlib_node.parm("fillmaterials").pressButton()
        self.matlib_node.setParms({"assign1": 1})

        # # assign material to each geometry
        # for index, key in enumerate(list(self.fbx_geos_shader_names.keys())):
        #     self.matlib_node.setParms({"geopath" + str(index + 1): "/Geometries/" + key })

        # Edit "shop_materialpath" to materialX

    
    def setupEachShader(self):
        for key, value in self.fbx_geos_shader_names.items():
            print("Processing: ", key)
            # Get current subnet
            current_subnet = hou.node("{0}/{1}".format(self.matlib_node.path(), key))
            if not current_subnet.allItems():            
                # Surface output
                output_surface = current_subnet.createNode("subnetconnector", "surface_output")
                output_surface.setParms({"connectorkind": 1, "parmname": "surface", "parmlabel": "Surface", "parmtype": "surface"})
                
                # Displacement output
                output_displacement = current_subnet.createNode("subnetconnector", "displacement_output")
                output_displacement.setParms({"connectorkind": 1, "parmname": "displacement", "parmlabel": "Displacement", "parmtype": "displacement"})
                
                # connect nodes
                output_displacement.createInputNode(0, "mtlxdisplacement", "mtlxdisplacement")
                mtlx_node = output_surface.createInputNode(0, "mtlxstandard_surface", "mtlx_material")
                mtlxuv = current_subnet.createNode("mtlxtexcoord", "mtlxtexcoord")
                mtlxuv.setParms({"signature": "vector2"})
                
                # Create and connect images

                # for img_index in range(len(self.mtlx_input_names)):
                for img_index in range(2):
                    current_img = mtlx_node.createInputNode(img_index, "mtlximage", self.mtlx_input_names[img_index])
                    current_img.setInput(1, mtlxuv, 0)
                    try:
                        current_img.setParms({"file": self.textures_folder + "\\" + self.fbx_geos_shader_names[key][img_index]})
                    except:
                        current_img.setParms({"file": ""})
                current_subnet.layoutChildren()
            
def execute():
    bmn = BuildMtlxNetwork()
    # bmn.getListOfFBXMaterials()
    bmn.getInfoAboutFBX()
    bmn.modifyFBX()
    bmn.getFilesInFolder()
    bmn.createReferenceGeometries()
    bmn.createShaderSubnets()
    bmn.setupEachShader()
