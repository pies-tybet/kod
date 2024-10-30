import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from shapely.geometry import Polygon, LineString, MultiPolygon, Point
from shapely.ops import unary_union  ### zwraca wartosc wielu wielokatow pod jendym pod combined_polygon
from shapely import intersects
from flask import Flask, request, jsonify
from flasgger import LazyJSONEncoder
from flask_cors import CORS
import base64
from io import BytesIO


app = Flask(__name__)
CORS(app)
app.json_encoder = LazyJSONEncoder

@app.route("/test")
def test():
    return "OK112"


@app.route("/roof_fill", methods=['POST'])

def Roof_fill():

    # Funkcja do generowania rysunku
    def draw_shape(vertices, rectangles, resolution, holes):
        print(holes)
        plt.ioff()
        fig, ax = plt.subplots()
        # Rysowanie wielokąta
        polygon_shape = patches.Polygon(vertices, closed=True, edgecolor='b', fill=None)
        ax.add_patch(polygon_shape)
        # Rysowanie okien
        
        
        for hole in holes:
            #            patches.Polygon( [150,250]     ,)
            hole_shape = patches.Polygon(hole, closed=True, edgecolor='b', fill=None)
            ax.add_patch(hole_shape)
        
        # Rysowanie kwadratów
        for rect in rectangles:
            ax.add_patch(rect)

        fig.set_figwidth(16)
        fig.set_figheight(9)
        ax.set_xlim([0, resolution['width']])
        ax.set_ylim([0, resolution['height']])
        ax.invert_yaxis()

        
        # Tworzenie bufora do przechowywania SVG w pamięci
        #fig.savefig(f"{name}_{mode}.svg")
        plt.axis('off')
        # Zapisywanie wykresu do bufora w formacie SVG
        svg_buffer = BytesIO()

        fig.savefig(svg_buffer, format='svg', bbox_inches='tight', pad_inches=0)

        # Przejście do początku bufora
        svg_buffer.seek(0)

        # Odczytanie zawartości bufora jako ciągu bajtów SVG
        svg_bytes = svg_buffer.getvalue()

        # Zamknięcie bufora
        svg_buffer.close()

        # Konwersja ciągu bajtów SVG do ciagu Base64
        svg_base64 = base64.b64encode(svg_bytes).decode('utf-8')
        # usuwanie wykresów z pamięci
        plt.close("all")
        plt.cla()
        plt.clf()

        return svg_base64
    
    # Funkcja główna do wypełniania kształtu prostokątami    
    def shape_into_points(poly, width, height, sizes, resolution, roof_type, installation_method, holes=[]):
        mixed = False
        if installation_method == "alternately":
            mixed = True

        poly_int = []
        for set in poly:
            set_int = []
            for point in set:
                set_int.append(int(point))
            poly_int.append(set_int)

        roof_poly = Polygon(poly_int, [])
        print(roof_poly)
        # Obliczanie ramki ograniczającej
        minx, miny, maxx, maxy = roof_poly.bounds

        smallest_element_width = min(sizes)
        half_panel_width = smallest_element_width / 2

        def point_intersects_hole(point, holes):
            point_obj = Point(point)
            for hole in holes:
                hole_polygon = Polygon(hole)
                if hole_polygon.contains(point_obj):
                    return True
            return False
        
        def polygon_intersects_hole(polygon, holes):
            for hole in holes:
                hole_polygon = Polygon(hole)
                buffered_polygon = hole_polygon.buffer(10, join_style=2)

                if buffered_polygon.intersects(polygon):
                    return True
            return False

        def polygon_intersects_buffer(polygon, holes):
            for hole in holes:
                hole_polygon = Polygon(hole)
                buffered_polygon = hole_polygon.buffer(10, join_style=2)

                if buffered_polygon.intersects(polygon):
                    return True
            return False
        
        # # Obliczanie optymalnej wysokości
        def optimal_height(min_height, max_height, total_height):
            output = 0
            current_length = min_height
            total_length = total_height
            while current_length <= max_height:
                fit_count = total_length / current_length
                if fit_count >= math.floor(output):
                    optimal_length = current_length
                    if fit_count < output:
                        optimal_length = current_length
                    output = fit_count
                current_length += 1
            return optimal_length

        roof_height_mm = abs(maxy - miny) * 10

        if roof_type == "K":
            optimalCoverageHeight = optimal_height(155, 165, roof_height_mm)
        else:
            optimalCoverageHeight = optimal_height(340, 360, roof_height_mm)

        # Generowanie punktów wewnątrz ramki z równymi odstępami
        rows = []
        row = {}
        y = miny

        # Open a file for writing points
        with open('points.txt', 'w') as file:
            while y <= maxy:
                points = []
                x = minx
                while x + width <= maxx:
                    if roof_poly.contains(LineString([(x, y), (x, y + height)])) and not point_intersects_hole((x, y), holes):
                        points.append((x, y))
                        file.write(f"{x}, {y}\n")  # Write point to file
                   
                    x += width
                if points == []:
                    x = minx
                    while x + width <= maxx:
                        if roof_poly.intersects(LineString([(x, y), (x, y + height)])) and not point_intersects_hole((x, y), holes):
                            points.append((x, y))
                            file.write(f"{x}, {y}\n")  # Write point to file
                        
                        x += width

                if points != []:
                    min_x = min(point[0] for point in points)
                    max_x = max(point[0] for point in points)
                    row = {'Points': points, 'Min': min_x, 'Max': max_x}
                    rows.append(row)
                y += height

        

        # Pętla wyznaczająca elementy aktywne i pasywne
        tolerance = 1e-2
        buffered_roof_poly = roof_poly.buffer(tolerance)
        rectangles = []
        right = 0
        ishole = False
        for index, row in enumerate(rows):
            current_y = row['Points'][0][1]
            while current_y <= maxy:
                current_x = row['Min']
                while current_x <= row['Max']:
                    if (current_x, current_y) in row['Points']:
                        #print(f"Current point: ({current_x}, {current_y})")
                        #print(f"Index: {index}")
                        if roof_type == "P":
                            if index % 2 == 0 and mixed:
                                if buffered_roof_poly.contains(Polygon([(current_x, current_y), (current_x + smallest_element_width, current_y), (current_x + smallest_element_width, current_y + height), (current_x, current_y + height), (current_x, current_y)])) and not polygon_intersects_hole(Polygon([(current_x, current_y), (current_x + smallest_element_width, current_y), (current_x + smallest_element_width, current_y + height), (current_x, current_y + height), (current_x, current_y)]), holes):
                                    rectangles.append(patches.Rectangle((current_x, current_y), smallest_element_width, height, linewidth=1, edgecolor=(0.1, 1.0, 0.0, 1), facecolor='none'))
                                    current_x += smallest_element_width
                            else:
                                if buffered_roof_poly.contains(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)])) and not polygon_intersects_hole(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)]),holes):
                                    rectangles.append(patches.Rectangle((current_x, current_y), half_panel_width, height, linewidth=1, edgecolor=(0.1, 1.0, 0.0, 1), facecolor='none'))
                                    current_x += half_panel_width
                        else:
                            if index % 2 == 1 and mixed:
                                if buffered_roof_poly.contains(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)])) and not polygon_intersects_hole(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)]),holes):
                                    rectangles.append(patches.Rectangle((current_x, current_y), half_panel_width, height, linewidth=1, edgecolor=(0.1, 1.0, 0.0, 1), facecolor='none'))
                                    current_x += half_panel_width
                        #dlugie
                        minHoleY = math.inf
                        maxHoleY = 0
                        if holes:
                            minHoleY = min(j[1] for i in holes for j in i)
                            maxHoleY = max(j[1] for i in holes for j in i)


                        while buffered_roof_poly.contains(Polygon([(current_x, current_y), (current_x + smallest_element_width, current_y), (current_x + smallest_element_width, current_y + height), (current_x, current_y + height), (current_x, current_y)])):
                            if not polygon_intersects_hole(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)]), holes) and ishole and right == 1:
                                rectangles.append(patches.Rectangle((current_x, current_y), half_panel_width, height, linewidth=1, edgecolor=(0.0, 1.0, 0.1, 1), facecolor='none'))
                                current_x += half_panel_width
                                ishole = False 
                                print("tak")
                                right = 0
                            elif polygon_intersects_buffer(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)]), holes) and not polygon_intersects_hole(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)]), holes) and not polygon_intersects_hole(Polygon([(current_x, current_y), (current_x + (2*half_panel_width), current_y), (current_x + (2*half_panel_width), current_y + height), (current_x, current_y + height), (current_x, current_y)]), holes) and not polygon_intersects_hole(Polygon([(current_x-half_panel_width, current_y), (current_x, current_y), (current_x, current_y + height), (current_x-half_panel_width, current_y + height), (current_x-half_panel_width, current_y)]), holes):
                                rectangles.append(patches.Rectangle((current_x, current_y), half_panel_width, height, linewidth=1, edgecolor=(0.0, 1.0, 0.1, 1), facecolor='none'))
                                current_x += half_panel_width 
                            elif not polygon_intersects_hole(Polygon([(current_x, current_y), (current_x + smallest_element_width, current_y), (current_x + smallest_element_width, current_y + height), (current_x, current_y + height), (current_x, current_y)]), holes):
                                rectangles.append(patches.Rectangle((current_x, current_y), smallest_element_width, height, linewidth=1, edgecolor='g', facecolor='none'))
                                current_x += smallest_element_width 
                            elif not polygon_intersects_hole(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)]),holes):
                                rectangles.append(patches.Rectangle((current_x, current_y), half_panel_width, height, linewidth=1, edgecolor=(0.0, 1.0, 0.1, 1), facecolor='none'))
                                current_x += half_panel_width
                                right = 1 
                            else:
                                current_x += smallest_element_width
                                ishole = True   
                           
                            
                            



                        #zielone na koncu
                        if buffered_roof_poly.contains(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)])) :
                            if not polygon_intersects_hole(Polygon([(current_x, current_y), (current_x + half_panel_width, current_y), (current_x + half_panel_width, current_y + height), (current_x, current_y + height), (current_x, current_y)]),holes):
                                print()
                                rectangles.append(patches.Rectangle((current_x, current_y), half_panel_width, height, linewidth=1, edgecolor=(0.0, 1.0, 0.1, 1), facecolor='none'))
                            current_x += half_panel_width

                        while intersects(roof_poly.boundary, Polygon([(current_x, current_y), (current_x + smallest_element_width, current_y), (current_x + smallest_element_width, current_y + height), (current_x, current_y + height)])):
                            intersection = roof_poly.intersection(Polygon([(current_x, current_y), (current_x + smallest_element_width, current_y), (current_x + smallest_element_width, current_y + height), (current_x, current_y + height)]))
                            area = intersection.area
                            current_x += smallest_element_width
                    else:
                        current_x += smallest_element_width  # Move to the next point if the current point does not exist in the row
                        #print("current_x: ", current_x, "current_y: ", current_y)
                        #print("Point does not exist in the row")
                current_y += height  # Move to the next row
                right = 0
        # Funkcja do scalania ze sobą prostokątów według koloru
        def merge_adjacent_rectangles(rectangles, sizes, color):

            # Sortowanie po y i po x żeby szło po rzędach
            rectangles.sort(key=lambda rect: (rect.get_y(), rect.get_x()))
            merged_rectangles = []
            i = 0
            while i < len(rectangles):
                current_rect = rectangles[i]
                merged = False
                for size in sizes:
                    if i + int(size/smallest_element_width) <= len(rectangles) and rectangles[i + int(size/smallest_element_width)-1].get_x()+smallest_element_width == current_rect.get_x() + size:
                        merged_rectangle = patches.Rectangle((current_rect.get_x(), current_rect.get_y()),
                                                        current_rect.get_width() * (size/smallest_element_width),
                                                        current_rect.get_height(), edgecolor=color, facecolor='none')
                        
                        merged_rectangles.append(merged_rectangle)
                        i += int(size/smallest_element_width)
                        merged = True
                        break
                if not merged:
                    i += 1
            return merged_rectangles
        
        # Podział prostokątów na odpowiadające im panele
        filtered_rectangles_row = []
        filtered_rectangles_active=[]
        filtered_rectangles_edge_left=[]
        filtered_rectangles_edge_right=[]
        filtered_rectangles_inactive=[]

        # Range dla step jako float
        def frange(start, stop, step):
            while start < stop:
                yield start 
                start += step

        for i in frange(miny,maxy,height):
            filtered_rectangles_row.append([rect for rect in rectangles if rect.get_y() == i])

        # Dla każdego wiersza rozdziela panele na poszczególne typy w zależności od ich koloru
        for row in filtered_rectangles_row:
            for rect in row:
                if rect.get_edgecolor() == (0.0, 0.5, 0.0, 1):
                    filtered_rectangles_active.append(rect)
                elif rect.get_edgecolor() == (0.1, 1.0, 0.0, 1):
                    filtered_rectangles_edge_left.append(rect)
                elif rect.get_edgecolor() == (0.0, 1.0, 0.1, 1):
                    filtered_rectangles_edge_right.append(rect)
                else:
                    filtered_rectangles_inactive.append(rect)

        # Grupowanie paneli
        rectangles_active=merge_adjacent_rectangles(filtered_rectangles_active,sizes,(0.0, 0.5, 0.0, 1))
        
        end_rectangles=rectangles_active
        rectangles_passive_edge=filtered_rectangles_edge_left+filtered_rectangles_edge_right
        end_rectangles+=rectangles_passive_edge

        # Generowanie rysunku
        draw=draw_shape(poly, end_rectangles, resolution, holes)

        # Zliczanie ilości odpowiednich paneli
        sizes_half=sizes.copy()
        sizes_half.append(int(half_panel_width))
        panels_count = {str(size): 0 for size in sizes_half}
        for size in sizes_half:
            for panel in end_rectangles:
                if panel.get_width()==size:
                    panels_count[str(size)]+=1
        
        
        # Pole dachu
        area=roof_poly.area

        # Zwracanie parametrów wszystkich paneli
        panels_values=[]        
        for panel in end_rectangles:
            if panel.get_edgecolor() == (0.0, 0.5, 0.0, 1):
                rect_type='active'
            elif panel.get_edgecolor() == (0.1, 1.0, 0.0, 1):
                rect_type='passive_left'
            elif panel.get_edgecolor() == (0.0, 1.0, 0.1, 1):
                rect_type='passive_right'
            panel_values={'x':panel.get_x(),'y':panel.get_y(),'width':panel.get_width(),'type':rect_type}
            panels_values.append(panel_values)
        

        return panels_values,panels_count,area,height,draw,optimalCoverageHeight





# Zczytanie danych wejściowych z jsona
    data = request.json
### GRUPOWANIE ### 
    input_groups = {}
    holes = []   
    for polygon in data["elements"]:
        group_id = polygon.get('group')
        if polygon.get('type') =="hole":
            holes.append(polygon['points'])
        else:

            if group_id not in input_groups:
                input_groups[group_id] = []
            input_groups[group_id].append(polygon['points'])
    
    combined_elements = []
    last_poly = None

    
    polygons_to_keep = []
    other_polys = []
    for group_id, group_polygons in input_groups.items():
        if len(group_polygons) > 1:
            print(group_polygons)
            polygons = [Polygon(p) for p in group_polygons]
            for polygon in polygons:
                 
                if last_poly is None:
                    last_poly = polygon
                    
                    polygons_to_keep.append(polygon)
                elif last_poly.intersects( polygon ):
                    last_poly = last_poly.union(polygon)
                    
                    polygons_to_keep.append(polygon)
                else:
                    other_polys.append(polygon)
            
            polygons = polygons_to_keep
            merged_polygon = unary_union(polygons)
            print(other_polys)
            if other_polys:
                for poly in other_polys:
                    isIntersecting = False
                    temp_poly = poly
                    l = 0
                    r = 0
                    u = 0
                    d = 0
                    print("other:" , other_polys)
                    print("merged:" , merged_polygon)
                    for i in range(11):
                        if isIntersecting:
                            #break
                            pass
                        temp_poly = Polygon([(x - i, y) for x, y in poly.exterior.coords])
                        if temp_poly.intersects( merged_polygon ):
                            #poly = temp_poly
                            l = i
                            isIntersecting = True
                            break
                    temp_poly = poly
                    for i in range(11):
                        if isIntersecting:
                            #break
                            pass
                        temp_poly = Polygon([(x + i, y) for x, y in poly.exterior.coords])
                        if temp_poly.intersects( merged_polygon ):
                           # poly = temp_poly
                            r = i
                            isIntersecting = True
                            break
                    temp_poly = poly
                    for i in range(11):
                        if isIntersecting:
                            #break
                            pass
                        temp_poly = Polygon([(x, y+i) for x, y in poly.exterior.coords])
                        if temp_poly.intersects( merged_polygon ):
                           # poly = temp_poly
                            d = i
                            isIntersecting = True
                            break
                    temp_poly = poly
                    for i in range(11):
                        if isIntersecting:
                            #break
                            pass
                        temp_poly = Polygon([(x, y-i) for x, y in poly.exterior.coords])
                        if temp_poly.intersects( merged_polygon ):
                          #  poly = temp_poly
                            u = i
                            isIntersecting = True
                            break
                    if isIntersecting:
                        print("r: "+str(r) )
                        print("l: "+str(l))
                        print("u: "+str(u))
                        print("d: "+str(d))
                        xdif = 0
                        ydif = 0
                        
                        xdif = r-l
                        
                        
                        
                        ydif = d-u
                        
                        
                        print("l"+str(l))
                        print("xdif: "+str(xdif))
                        print("ydif: "+str(ydif))
                        poly = Polygon([(x + xdif, y + ydif) for x, y in poly.exterior.coords])



                        if isIntersecting:

                            merged_polygon = merged_polygon.union(poly)
                    # minx2 = min(point[0] for point in poly.exterior.coords)

                    # minx1 = max(
                    #             point[0]
                    #             for point in merged_polygon.exterior.coords
                    #             if point[0] <= minx2
                    #             )
                    # distance = minx2 - minx1
                    # buffered = merged_polygon.buffer(10, join_style=2)
                    # if buffered.intersects( poly.buffer(10, join_style=2) ):
                    #     poly = Polygon([(x - distance, y) for x, y in poly.exterior.coords])
                    #     merged_polygon = merged_polygon.union(poly)

            if isinstance(merged_polygon, MultiPolygon):
                for poly in merged_polygon:
                    combined_elements.append(poly)
            else:
                combined_elements.append(merged_polygon)
        else:
            combined_elements.append(Polygon(group_polygons[0]))

# -------------------- #

   
    panel_widths = data['roofWidths']
    panel_height = data['roofHeight']
    resolution = data['resolution']
    installation_method = data['installationMethod']
    roof_type = data['roofType']
    width_unit = 1


    # Tworzenie obiektu dla elementów i wypełnienie go

    elements = []
    # interacja po combined_polygon zamiast po ###for i in range(len(input_names)):
    for combined_polygon in combined_elements:
        vertices = list(combined_polygon.exterior.coords)
        panels_values, panel_count, roof_area, optimal_height, illustration, optimalCoverageHeight = shape_into_points(vertices, width_unit, panel_height, panel_widths, resolution, roof_type, installation_method, holes)

        panel_area = sum(size * optimal_height * panel_count[str(size)] for size in data['roofWidths'])
        coverage = round((panel_area / roof_area) * 100, 2)
        element = {'id': f'group_{group_id}', 'roof_vertices': vertices, 'panel_count': panel_count,'panel_area': panel_area,
            'roof_area': roof_area, 'area_covered_percentage': coverage, 'image': illustration,'panel_parameters': panels_values,
            'optimal_coverage_height': optimalCoverageHeight, 'shape': 'combined', 'path': ''  
        }
        elements.append(element)

    output = {'elements': elements} 
    return jsonify(output)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5031, ssl_context='adhoc') #ssl_context='adhoc'

# Scalenie przecinającyh się brył / overlapping
# !!! info w readme.txt