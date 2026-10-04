> Demo files are in `samples/`. `Drawing-detail-demo.FCStd` is not included in this first public package.

# FluxCAD

FluxCAD is a Windows workspace built on FreeCAD, with a compact ribbon and modeling workflows inspired by Fusion. It is an independent prototype, not an Autodesk product. FreeCAD 1.1.3 is the tested version.

## Start

Install FreeCAD, extract the FluxCAD folder to a writable location, and run `Start-FluxCAD.cmd`. The launcher first checks installed FreeCAD versions under Program Files, then `runtime/bin/FreeCAD.exe`. To specify another installation, use:

```powershell
.\Start-FluxCAD.ps1 -FreeCADPath "C:\path\to\FreeCAD\bin\FreeCAD.exe"
```

FreeCAD supplies Python and the CAD engine. The FluxCAD folder alone does not include the FreeCAD application.

## Language

The initial FluxCAD language is Japanese. Choose **設定 → 表示言語 / Language → English** in the upper right, save your work, and restart FluxCAD. This also selects English for the native FreeCAD interface. To switch back, use **Settings → Language → 日本語** and restart.

The choice is remembered in the local `config` folder. Existing document and object names are kept as written. Changing language does not cancel the active operation or change the camera. New objects receive default labels in the selected language.

## Surfaces and sections

The **Surface** tab exposes native FreeCAD surface features.

- **Create → Extrude / Revolve** uses whole sketches or curves, with length/direction or axis/angle controls. Open profiles are supported. Closed profiles produce surfaces without end caps.
- **Create → Loft** connects complete profiles, including closed four-edge rectangles. Ctrl-select sketches/curves in order in the browser; add, remove or reorder sections in the native task lists.
- **Create → Sweep** starts with the profile sketch/curve. In the native task, press **Sweep Path**, select the path edges, press **Done**, then confirm with OK. Select the profile and path separately.
- **Create → Patch** fills a closed boundary, including nonplanar boundaries. Ctrl-select the boundary edges, or preselect an entire closed sketch. Adjust boundaries, support faces and continuity in the native task, then confirm with OK.
- **Create → Boundary Surface** creates a face from 2 to 4 boundary curves. Curve order, orientation and connectivity must be suitable; adjust the selection in the native task.
- **Create → Surface from Sections** creates a surface through ordered edges. Ctrl-select the edges in section order. Each section is one edge; this differs from lofting complete multi-edge closed profiles.
- **Modify → Extend Face** extends one face in its local U−/U+/V−/V+ directions. Enter percentages of the original parameter range, rather than distances in mm. For a 20×10 mm plane, U+10% and V+20% produce 22×12 mm. Preview the result, confirm with OK or restore it with Cancel. Curved faces are supported; this is parameter-range extension rather than distance-based extension of arbitrary boundary edges.
- **Modify → Offset Surface** offsets a whole surface or selected faces of one body by a signed normal distance in mm. Positive follows the normal and negative goes the other way. Preview shows the position and area. Select faces rather than edges or an entire solid.
- **Modify → Thicken** fills between the source and offset surface to create a new body. A 20×10 mm plane thickened by 2 mm gives 400 mm³. Signed distance controls direction, including on curved faces. The result must be one connected solid; collapsing offsets and self-intersections are not repaired. When thickening body faces, the original body remains: hide it with the browser eye icon when needed.
- **Modify → Refine Shape**, also under Solid > Modify, removes redundant boundaries such as coplanar seams from selected whole shapes. It works on connected surfaces or solids; it does not stitch separate faces or fill holes. The hidden source remains linked, and the result follows its changes.
- **Inspect → Section Analysis (Clipping)** reveals the interior without changing model geometry. Enable X, Y, Z or a custom-direction plane, then adjust its position and direction. Uncheck the planes to restore the full view. This is a viewing tool rather than a saved section shape.
- **Inspect → Create Cross Sections** creates section curves from selected shapes at an XY, XZ or YZ plane. Repeated sections support count, spacing and both-side options. The resulting curves are snapshots: recreate them after changing the source body.

The browser lists faces in **Surfaces** and section curves/imported wires in **Curves**. Use the eye icon for visibility and the context menu for measurement, appearance or export. Double-click a Patch, Boundary Surface or Surface from Sections to edit its native task. Press **Add Edge** before selecting additional edges. Cancel and native Undo/Redo are supported. Finishing a sketch returns to the tab that was active before editing.

Double-click an Extrude, Revolve, Loft, Sweep or Extend result in the browser/history to open its movable parameter editor. Edit extrusion lengths, taper and symmetry; revolution angle and axis; loft ruled/closed settings; sweep Frenet; or U/V extension percentages. Preview, Cancel and Undo/Redo are supported. Replacing profile/path references is not exposed in this editor: edit the source sketch or create a new feature. Surface creation keeps the native **Create solid** option disabled.

Offset results appear in **Surfaces**, and thickened solids in **Bodies**. Double-click a result in the browser/history to edit distance and corner join (Arc or Intersection). Drag the dialog title bar to move it. Preview, Cancel and Undo/Redo are supported, and an already moved result retains its placement during editing. Selected body faces use native reference objects and follow source dimensions and placement.

Surfaces and curves can be exported as STEP. Surfaces can also be exported as STL, though a surface mesh need not form a closed solid. Curves and points cannot be represented by STL.

`Surface-sections-demo.FCStd` includes a nonplanar patch, a four-edge face, a surface through semicircular sections and section curves at Z=1/2/3 mm. `Surface-modeling-demo.FCStd` includes extrusion, half revolution, a four-edge profile loft, sweep and planar extension. `Surface-finishing-demo.FCStd` contains a negative offset surface, a moved plate with edited thickness, inward cylinder-face thickening, and refined surface/solid examples. All use native FreeCAD features, recompute in ordinary FreeCAD and follow source sketch, curve or face changes. Surface sewing remains future work.

## Measurement, geometry checks, scale and appearance

- **Solid → Inspect → Measure** opens the native FreeCAD measurement panel. Select edges, faces or points; Ctrl-select two vertices to measure their distance. The mode selector also offers length, angle, area and radius. **Save** keeps a measurement in the browser's **Measurements** group. Double-click it for values, use the eye icon to toggle visibility, or right-click to delete it. Unsaved measurements disappear when the panel closes.
- **Inspect → Measure (dimensions / volume)** retains the existing bounding dimensions, volume and surface-area summary. Meshes show their dimensions and triangle count.
- **Inspect → Check Geometry** validates selected shapes. Choose the native check settings, then click **Run check** and inspect the invalid-shape count. This checks geometry without repairing or modifying it.
- **Solid → Modify → Scale** creates a native `Part::Scale` feature with a uniform factor or separate X/Y/Z factors. Choose **Apply** or **OK** to create the result; the source remains in the history. Double-click the resulting body or its Scale history item to edit the factors. OK applies changes, Cancel leaves the feature unchanged, and Ctrl+Z undoes an edit. Arbitrary reference-point selection is not yet offered.
- **Solid / Mesh → Modify → Appearance** opens native display settings for selected objects, including transparency, line width, colors and display style. Dimensions remain unchanged. Appearance is saved in FCStd, not STL.

Finish or close an active native task before starting another operation. Measurement and appearance use FreeCAD's standard task controls.

`Scale-inspection-demo.FCStd` scales a 20×10×5 mm box by X/Y/Z factors 2/3/4, producing a 40×30×20 mm result. It includes a saved 20 mm distance measurement and 45% transparency. Ordinary FreeCAD can recompute the model.

## Basic workflow

### Offset Plane from a face

Use **Solid → Construct → Offset Plane**. Choose XY, XZ, YZ or **Selected Face** as the reference. With Selected Face, press **Reference Face** and click a planar solid face or construction plane. A preselected face or whole construction plane is filled in automatically. Slanted planar faces are supported; curved faces are rejected.

Enter a signed perpendicular distance in mm. The green arrow indicates the positive direction; a negative value creates the plane on the other side. Zero is also supported. World XY/XZ/YZ use +Z/+Y/+X respectively. Selected faces use their oriented normal, which may point inward on a cavity or downward on an underside. Numeric input accepts six decimal places without grid rounding.

Confirm to add the plane to **Construction** in the browser. Select it and use **Create Sketch** to draw on it. The plane, sketch and subsequent extrusion follow source dimensions, translation and rotation. **Display Size** changes only the visible patch and does not move the sketch origin or limit where you can draw. Double-click the plane in the browser or timeline to edit its reference, distance or size. Reselect the reference to repair a missing or invalid face.

The movable panel reaches either edge, collapses and scrolls. Creating or editing a plane preserves the camera and zoom. Cancel / Esc discards the preview, and Ctrl+Z undoes a confirmed operation. **Start FluxCAD before opening saved FCStd files containing new offset planes.** Older native FreeCAD offset planes retain their existing reference-plane and distance editor. `Face-offset-demo.FCStd` demonstrates a 12 mm offset from a tilted face with an attached sketch and extrusion. Curved-face offsets and an Up to Point mode are not included.

### Midplane and Plane at Angle

Open **Solid → Construct → Midplane** or **Plane at Angle**.

- **Midplane:** select two parallel planar faces. They can belong to the same body, different bodies, or construction planes. Use the Face 1 / Face 2 buttons to pick in the view, or preselect both faces with Ctrl before opening the command. Bisectors between nonparallel faces are not supported.
- **Plane at Angle:** choose XY, XZ, YZ or a selected planar face as the reference plane. Choose X, Y, Z or a selected straight edge as the rotation axis, then enter an angle from −180 to 180 degrees. The axis must lie in the reference plane. For example, choose a box's top face and one of its straight boundary edges. Positive and negative angles tilt to opposite sides of the axis.

Confirm the preview to add the plane to the browser's **Construction** group. Select it and use **Create Sketch** to draw on it. The visible square is only a display patch: sketches can extend beyond it. **Display Size** changes this patch without moving the sketch origin.

The planes, attached sketches and subsequent extrusions follow reference dimensions and placement. Double-click a plane in the browser or timeline to edit its references, angle and size. Missing references or incompatible face/axis geometry produce an error; reselect references to repair it. Panel edits that invalidate later features are rolled back.

The panel can move to either edge, collapse and scroll. Creating or editing a plane preserves the camera and zoom. Cancel / Esc removes the preview; Ctrl+Z undoes a confirmed change. **Start FluxCAD before opening saved FCStd files** to restore these linked plane features. `Construction-planes-demo.FCStd` includes both plane types, attached sketches and an extrusion.

### Tangent Plane

Choose **Solid → Construct → Tangent Plane**, then click a cylindrical or conical side face. The clicked position sets the initial angle; enter an angle from −180 to 180 degrees to adjust it. You can also preselect a curved face. Use **Curved Face** to replace the reference. Angles are measured from the selected surface's reference direction, which is not necessarily world X.

The green point marks contact and the arrow shows the positive normal. **Flip Normal** reverses it. Inner cylindrical faces follow the original inward normal. Confirm to add the plane to the browser's **Construction** group, then select it and use **Create Sketch**. Use that sketch as the basis for side-facing extrusions or cuts.

The plane, attached sketch and extrusion follow source radius and placement changes. Cylinder height and **Display Size** changes preserve the sketch origin. Cone height or radius changes can change its slope and therefore the plane's orientation. The display patch does not limit where you can sketch. Flip Normal retains the origin and X direction, reversing Y and Z.

Double-click the plane in the browser or timeline to edit the face, angle, size and normal. The panel moves to either edge, collapses and scrolls without changing the camera or zoom. Cancel / Esc discards the preview; Ctrl+Z undoes confirmation.

Analytic cylindrical and conical faces are supported. Spheres, tori, freeform surfaces and STL meshes are not supported. On partial faces, choose an angle covered by the face. Deleted or incompatible references clear the plane and show an error; reselect the face or angle to recover it. **Start FluxCAD before opening saved FCStd files.** `Tangent-plane-demo.FCStd` contains cylinder and cone examples with attached sketches and extrusions.

### Plane Through Three Points

Choose **Solid → Construct → Plane Through Three Points**, then click three solid vertices or sketch endpoints. Picking advances from Point 1 to Point 2 to Point 3. Use the corresponding buttons to replace references. You can combine different bodies, sketches and standalone vertex objects, or preselect three vertices with Ctrl. Check their order in the panel and numbered preview markers.

Point 1 defines the sketch origin, and Point 1 → Point 2 defines X. The green arrow shows the positive normal; **Flip Normal** reverses it while retaining the origin and X direction. Coincident or collinear points cannot define a plane. Circle centers, arbitrary positions along edges, mesh vertices and direct point-coordinate input are not supported.

After confirming, select the plane in the browser's **Construction** group and use **Create Sketch**. Source dimension and placement changes update the plane, attached sketches and subsequent extrusions. **Display Size** changes only the visible patch, without moving the origin or X direction. You can sketch beyond that patch.

Double-click the plane in the browser or timeline to edit its three references, display size and normal. The panel can move to either edge, collapse and scroll without changing the camera or zoom. Cancel / Esc removes the preview; Ctrl+Z undoes confirmation. Deleted references or collinear source points clear the invalid plane; reselect points or repair the source geometry to recover it.

**Start FluxCAD before opening saved FCStd files.** `Three-point-plane-demo.FCStd` includes a plane through corners of three different-height columns, an attached sketch and an extrusion.

### Plane Along Path

Choose **Solid → Construct → Plane Along Path**, then click a sketch line, arc, spline or solid edge. The plane is perpendicular to the tangent at the specified position. Select a sketch in the browser to use its entire connected path, or choose an edge and press **Use Entire Path**. A whole solid cannot be used as a path.

- **Proportional:** 0% is the start and 100% is the end. A 50% plane stays halfway along the path when its length changes.
- **Distance:** enter the distance along the path in mm, with six decimal places. This uses arc length rather than straight-line distance and retains the numeric value after path length edits.
- **Measure from End:** measure in the opposite direction; the positive normal also follows the reversed traversal. Blue **S** marks the measuring start and the green arrow shows the plane normal.
- **In-plane Rotation / Flip Normal:** adjust sketch orientation. Flip Normal retains the origin and X direction while reversing Y and Z.

Confirm to add the plane to the browser's **Construction** group. Select it and use **Create Sketch** to draw a section. Several sections on path planes can be joined with Loft. Editing the position or source path updates the plane, attached sketch and dependent features. **Display Size** changes only the visible patch and does not move the origin.

Lines, arcs, closed circles, splines and connected multiedge paths are supported. Disconnected or branched paths and STL meshes are unsupported. An exact sharp corner has no unique perpendicular plane; choose a position before or after the corner. Closed paths start at their existing seam, with 0% and 100% at the same position. Distances exceeding the path length cannot be confirmed.

Double-click the plane in the browser or timeline to edit the reference, position and orientation. The panel moves to either edge, collapses and scrolls without changing the camera or zoom. Cancel / Esc discards the preview; Ctrl+Z undoes a confirmed operation. A deleted source or a path shortened below the requested distance clears the plane and displays an error. Reselect the path, change the position or repair the source to recover it.

**Start FluxCAD before opening saved FCStd files.** `Path-plane-demo.FCStd` includes planes at 0%, 50% and 100% along an arc, attached section sketches and a loft joining them.

### Sphere, Torus, Coil and Pipe

Choose **Solid → Create → Sphere / Torus / Coil / Pipe**. Enter dimensions and XYZ position, check the preview and confirm. Each operation creates a new body; use Combine or Cut for subsequent boolean operations. The camera and zoom stay unchanged. Double-click the body in the browser or timeline to edit it again. Existing rotations are preserved; use Move / Copy to change orientation. The panel can move to the edges, collapse and scroll. Cancel / Esc discards the preview, and Ctrl+Z undoes a confirmed creation or edit.

- **Sphere:** diameter and center position.
- **Torus:** centerline diameter and circular section diameter. Outside diameter = centerline diameter + section diameter.
- **Coil:** centerline diameter, round-wire diameter, pitch, turns and winding direction. Centerline height = pitch × turns. Fractional turns from 0.25 to 50 are supported. Ends are perpendicular to the wire; flat-ground spring ends, other section shapes and variable pitch are not included. Touching turns cannot be confirmed.
- **Pipe:** outside diameter and wall thickness. Select Straight to specify length and X/Y/Z axis, or select a sketch containing one connected path. A preselected sketch is filled in automatically. Arc, closed circular and spatial wire paths are supported and remain linked to source dimensions and placement. Sharp corners use miter joints. Disconnected or branched paths and self-intersecting tubes are unsupported. Inside diameter = outside diameter − 2 × wall thickness. Ends are not capped. Noncircular sections and collecting individual solid edges as a path are not included.

Torus, coil and straight pipe offer an X/Y/Z axis when created. XYZ for a path pipe is an additional offset from the source path. Spheres and tori use native FreeCAD features; coils and pipes use `model_primitives.py`. **Start FluxCAD before opening saved FCStd files.** Finished solids can be exported to STEP/STL. `Primitives-demo.FCStd` contains examples of all four types.

### Sketch to solid

Regions may be bounded by a rectangle and crossing arcs, B-splines or lines, including curves connected to rectangle vertices and closed caps outside the rectangle. Choose **Finish Sketch → click inside the region → E**. Ctrl+click adds or removes regions in the same sketch. Construction geometry and dangling lines do not create separate regions; small gaps are not closed automatically. Combining regions across separate sketches is unsupported.

Curved-region extrusions remain linked to the sketch and recompute after reopening in standard FreeCAD without the FluxCAD workspace. Changes that add/remove edges or change the number of intersections may require selecting the region again and rebuilding the operation.

1. Choose **Create Sketch**, select a plane, and draw a closed contour.
2. Choose **Finish Sketch**, click inside the desired profile, and press **E** to extrude. Ctrl+click selects multiple profiles in the same sketch.
3. Preview the distance and operation, then choose **OK**. Press Esc or Cancel to discard the preview; Ctrl+Z undoes a confirmed operation.

Middle-drag pans, Shift+middle-drag orbits, and the mouse wheel zooms. Press **M** to drag selected bodies or enter precise coordinates, **S** to search commands, **F** for Fillet, and **H** for Hole.

You can also **left-drag the view cube at the top right to orbit**. Release to keep that angle; zoom, model placement and selection stay unchanged. Short clicks on its faces, edges and corners still select standard views, and the surrounding arrows retain their usual behavior. Cube navigation also works in sketch editing, Move mode and modeling or mesh previews. Esc stops a cube drag at its current angle.

Use **Modify → Move / Copy (Rotate)** for world-axis rotation and independent copies. **Modify → Align** aligns two planar faces or the axes of two cylindrical side faces. Alignment does not create a joint or an ongoing constraint.

The browser separates bodies, sketches, construction planes and meshes. Double-click a sketch to edit it. The browser and sketch palette can be dragged and collapsed. Use **Settings → View → Show Bottom Tabs** to control the document tabs and design history.

The sketch palette automatically avoids the native sketch tasks and browser. Drag its title to place it manually, including over native side panels and all the way to either window edge. Its position stays between the ribbon and bottom tabs and is preserved during refresh, when reopening sketch edit, and after restart. Resizing keeps it within the working area. Click the title to collapse or expand it; right-click and choose **Reset Automatic Position** to return to placement that avoids the other panels.

### Sketch grid snapping

**Snap to grid** and **Stronger grid snapping** in the sketch palette are enabled by default. Stronger snapping makes nearby grid intersections easier to capture when drawing lines, rectangles, arcs and other sketch geometry. Existing vertices and edges keep priority. Numeric input, ordinary selection and dragging are unchanged. Turn stronger snapping off to restore the narrower native capture range; both settings persist after restart.

To change a displayed 5 mm interval, type a new value directly into **Grid spacing**, even while **Automatic grid spacing** is on. Press Enter or move to another field to apply it and switch to fixed spacing. Partial decimal entries survive palette refreshes. The palette also has **0.1 mm**, **0.5 mm** and **1 mm** buttons for immediate fixed spacing. You can enter custom intervals in increments of 0.001 mm. Turn **Automatic grid spacing** on to follow zoom again. The same input and presets are available in **Settings → View → Grid Settings**; OK applies the dialog's choices and Cancel leaves the grid unchanged.

The displayed grid and snap interval match; automatic spacing changes both with zoom, while fixed spacing stays unchanged. Zoom in if adjacent grid points overlap on screen. The shared grid retains its spacing and origin when entering or leaving sketch edit, including sketches on translated or tilted planes.

## Extrusion extents

Select a sketch or its closed profiles and press **E**. Choose an **Extent**:

- **Distance** retains numeric lengths and One Side, Reverse, Symmetric and Two Sides.
- **To Face (Plane)** lets you click a planar solid face or a visible construction plane as the end reference. Use **Select End Face** to choose again. One Side and Reverse are supported. An angled end plane produces an angled cap; the plane extends beyond the finite face boundary. Curved faces, planes parallel to the extrusion direction, and offset end planes crossing the starting profiles are unsupported.
- **Through All** selects **Cut** and computes its reach from the target body. It defaults to **Both Directions**, cutting on both sides of the start plane. One Side or Reverse cuts only on that side. No length input is required.

**Start Offset** shifts the extrusion's start plane without moving its sketch. Zero starts at the sketch; positive moves along the sketch's forward normal and negative moves backward. On an XY sketch, Start Offset 5 mm and Distance 10 mm produces Z=5 to 15 mm with One Side, Z=-5 to 5 mm with Reverse, or Z=0 to 10 mm with Symmetric. Changing Direction keeps the same start plane. Inputs range from -100000 to 100000 mm with 0.001 mm precision.

Lengths, symmetry and taper are measured from the shifted start plane; the gap from the sketch is not filled. On tilted sketches the offset follows the sketch normal. All extents support Start Offset: To Face reaches the end plane from the shifted start, and Through All cuts from that start toward the chosen side or both sides. An offset end plane at/before the start or an empty cutting direction is rejected.

Double-click an offset extrusion in history or its final body in the browser to edit the offset, including returning to zero. Source changes, save/reopen and Undo/Redo are supported. Older associative extents and tapered extrusions default to zero until edited. Ordinary native distance extrusions retain their existing length editor.

**To Face** also provides **End Offset**. Zero reaches the reference plane, +2 mm extends 2 mm beyond it, and -2 mm stops 2 mm short. Distance is measured along the extrusion direction; in Reverse, positive extends farther in that reverse direction. An angled end plane shifts parallel to itself along that axis, so this is not a perpendicular clearance measurement for angled faces.

Combine both offsets: from an XY sketch toward a plane at Z=20 mm, Start Offset 5 mm and End Offset -2 mm produces Z=5 to 18 mm; End Offset +2 mm produces Z=5 to 22 mm. End Offset ranges from -100000 to 100000 mm with 0.001 mm precision. The reference face stays unchanged and the extrusion follows its movement while retaining the specified offset.

End Offset supports New Body, Join, Cut, Intersect, history editing, save/reopen and Undo/Redo. Older features default to zero. It is unused for Distance and Through All, and is reset to zero when either extent is committed. Ends at/before the starting profile or crossing it are rejected. It can be combined with Taper Angle.

**Distance**, **To Face** and **Through All** provide **Taper Angle**. Zero keeps vertical walls; positive widens the end and negative narrows it. A 10° taper over 5 mm offsets each side by about 0.882 mm. Reverse uses the same sign convention. With Distance, Symmetric tapers both halves away from the start plane by the same angle, and Two Sides provides a separate **Reverse Taper** angle.

To Face trims the tapered end to the selected plane, including tilted planes, and supports Start Offset and End Offset together. Through All cuts a tapered shape through the target thickness; Both Directions applies the same angle away from the start plane in each direction. Changing the extent retains the taper angle.

Taper supports New Body, Join, Cut and Intersect (Through All is Cut only). Hole walls taper too: a positive angle expands the outer boundary and narrows holes. Adjacent selected cells merge before tapering. Angles range from -89° to 89°, but a collapsing or intersecting profile/hole, or an offset that changes the edge count, is rejected. The profile must remain intact through termination, and the taper and end-plane tilt must allow a finite closed solid. Reduce the angle or distance, or adjust the end plane, if the shape cannot be built.

Double-click a tapered extrusion in history, or its final body in the browser, to edit angles and lengths, including returning to zero taper. Source dimension changes, save/reopen and Undo/Redo are supported.

To Face follows movement of the end plane; Through All follows changes in target thickness and placement. Both retain links to the selected sketch profiles, including intersecting regions and profiles with holes. Disconnected New Body regions become independently editable bodies. Changes that remove or rearrange the referenced faces or contours may require reselection or rebuilding.

Double-click the new extrusion in history to reopen its panel. If it is the body's last operation, double-click that body in the browser or choose **Edit Extrusion…**. Edit extent, direction, end reference or distance while preserving the result's moved placement. The source profiles, operation and target body stay fixed when editing. Older distance extrusions keep their existing history length editor.

Preview before confirming; Cancel/Esc preserves the model, and Ctrl+Z undoes the operation. Associative extents, tapered extrusions and offset extrusions require `model_extents.py`, `model_taper.py` and their dependencies for recomputation: start FluxCAD before opening the saved FCStd. Export STEP or STL when sharing the finished geometry.

## Coaxial alignment

Open **Solid → Modify → Align**, then click the cylindrical side face of the moving body and the cylindrical side face of the target. The panel automatically switches to **Align — Coaxial**. Select the curved side rather than a flat end cap or circular edge. Inner hole walls and partial cylindrical faces are supported. Different radii can be aligned without resizing either body.

- **Match Axial Midpoints** matches the middle of each selected face's axial range, rather than the center of the whole part.
- **Keep Axial Position** aligns the axes while retaining the source's axial coordinate along the target axis, then adds the specified offset.
- **Axial Offset** moves along the target axis in mm. The green **+** arrow marks the positive direction. Surface construction can change this direction; it is not necessarily world +Z. Numeric input supports six decimal places without grid rounding.
- **Axial Rotation**, **Flip**, **+90°**, **Swap Faces** and **Create Copy** adjust orientation and allow independent copies. The original source and target remain unchanged when copying.

Confirm applies one undoable placement change. Cancel or Escape restores the original display and selection. The panel can be dragged to either window edge and collapsed from its header; its position is remembered. Camera and zoom do not change automatically, and navigation remains available during preview.

Mixed plane/cylinder pairs, cones, spheres, edges, vertices and same-body alignment are rejected. The operation does not check collisions or fit, resize diameters, or create a persistent joint. Already-matching placements are not changed, but Create Copy permits a duplicate at the same location. Later changes to the target do not move the aligned body. Native objects retain editable dimensions and save their placements for standard FreeCAD; copies are independent snapshots.

## Combine, Cut and Intersect

Choose **Solid → Modify → Combine / Cut / Intersect**. Select one **Target Body** and one or more **Tool Bodies**, preview the result, then confirm. Ordered preselection uses the first body as the target and the remaining bodies as tools; you can also open the command with no selection and pick in the viewport.

Use the target dropdown or **Pick Target**. Check tools in the list, or choose **Pick Tool Bodies** and click bodies to add/remove them; Ctrl-click also works. Choose **Finish Tool Selection / Preview** when ready. **Combine** joins the input material, **Cut** subtracts the tools from the target, and **Intersect** retains the target overlapping the union of all tools. Disjoint tools can therefore leave several separate intersecting portions.

**Keep Tool Bodies** retains independent tool entries in the browser after confirmation. With it off, tools become part of the consumed history. Both modes preserve dependencies: later changes to source dimensions or placements recompute the result. The blue preview shows the boolean result; retained tools are displayed after confirmation. Results containing multiple disconnected solids remain one browser item.

Double-click history or the final body, or use **Edit Operation and Tools…**, to change operation, tool selection and retention. The original target stays fixed during editing; the result's moved/rotated placement, custom name and color are preserved. Picking exposes the original inputs temporarily. Removed tools return as independent bodies if no other operation consumes them. Edits that break downstream geometry are rolled back.

Confirmation is one Undo step. Cancel/Esc, a different command or document switching restores visibility and selection without changing the camera. Drag the panel title to either edge or click to fold. If source geometry changes while the panel is open, cancel and reopen it. Meshes, duplicate inputs, earlier/later features of the same body and cyclic references are rejected. A cut must remove material; an empty result cannot be confirmed.

New operations use `model_combine.py`: **start FluxCAD before opening their saved FCStd files**. Older immediate Combine/Cut results remain native FreeCAD features. Export STEP/STL to share finished geometry.

## Split Body

Use **Solid → Modify → Split Body** to divide one connected solid into two independent bodies using a plane.

1. Select the body before opening the command, or use the Body dropdown.
2. Choose XY, XZ or YZ and enter an offset in mm. Principal-plane defaults center the cut on the body's bounding box.
3. For another plane, choose **Selected Face / Plane**, press **Select Face / Plane**, and click a planar face or construction plane. You can also preselect a body and a construction plane before starting. The face is extended across the entire body.
4. Positive offsets follow the reference normal; negative offsets go the other way. For example, a negative offset from a box's top face moves the cut inward. **Center on Body** centers it automatically.
5. Review the blue and orange bodies, then confirm. **Show Splitting Plane** toggles the plane overlay.

The browser lists the two results separately for moving, rotating, further modeling, and STEP/STL export. The original body remains hidden in history. Double-click the single Split Body history entry to edit its plane and offset. A newly split body also opens the shared editor from a browser double-click or **Edit Split…**. Each body's placement, appearance and visibility survive edits. Deleted outputs are not automatically recreated.

Source dimensions and reference-plane changes recompute the results. An edit that breaks a later feature is rolled back. Creation and editing support one-step Undo/Redo. Cancel, Escape, switching commands, or changing documents removes temporary previews and restores visibility. Drag the panel header to move it to either window edge, or click it to collapse. Opening and editing do not automatically change the camera or zoom.

This first version requires one connected input solid and one connected result on each side. Tangent or missed planes and cuts creating more than two pieces are rejected. Curved splitting surfaces, sketch-outline splits and meshes are not supported. Large topology changes may require reselecting a reference face. The split uses custom Python proxies in `model_split.py`; start FluxCAD before opening an FCStd file for recomputation or editing. Export STEP/STL to share the finished geometry.

## Fillet and Chamfer

Choose **Solid → Modify → Fillet** (F in the viewport) or **Chamfer**. Preselect edges to start with a preview, or select a body and pick its edges after opening the panel. With no selection, click a visible edge on a current body to choose the source.

**Select Edges** shows the original shape: click to select one edge, Ctrl-click to add/remove edges, then choose **Finish Selection / Preview**. The list's checkboxes also add/remove edges. Numbers and lengths refer to the original source edges; selected edges are orange during selection. Rotate the view to select edges on the back, or use the list.

Change **Radius** for Fillet. For Chamfer, choose **Chamfer Type → Equal Distance** or **Two Distances**. Equal Distance uses the same distance on both adjacent faces. Two Distances lets you enter, for example, **Distance 1 = 1 mm** and **Distance 2 = 3 mm**, measured along the adjacent faces. **Swap Distances 1 and 2** reverses the cut. All selected edges share the same pair of distances, and swapping applies to all of them. The face associated with each distance can differ between edges, so check the preview. Chamfer inputs support six decimal places.

The preview updates as dimensions and checkboxes change. An empty selection or an impossible size disables confirmation and displays a reason. The document geometry stays unchanged until Confirm. Cancel/Esc restores visibility and selection; Ctrl+Z undoes the whole operation.

Double-click the history entry to re-edit its edges, dimensions and chamfer type. If it is the body's last operation, double-click the browser body or use **Edit Edges and Dimensions…**. Re-editing preserves moved/rotated placement and supports older native constant-radius fillets and equal/two-distance chamfers with matching dimensions across all edges. Source dimensions remain linked; changing the source while the panel is open requires explicit edge reselection. Edits that invalidate downstream geometry are rolled back.

Drag the title to move the panel, including to the left edge; click its title or arrow to collapse it. Position is remembered independently of the Hole panel. Middle-button navigation and the view cube remain available, without automatic camera or zoom changes.

The tool supports one connected solid, constant-radius fillets and equal/two-distance chamfers. Variable radii, different dimensions for individual edges, angle-based chamfers, automatic tangent-chain selection and direct mesh editing are not included. Native FreeCAD features save and recompute without FluxCAD. Major source topology changes may require checking/reselecting the edges.

`Chamfer-distances-demo.FCStd` compares a blue 2 mm equal-distance chamfer, a green 1×5 mm chamfer and a purple 5×1 mm chamfer. Double-click each body in the browser to edit its dimensions.

## Face-based holes

Choose **Solid → Create → Hole**, or press **H**, then click a planar solid face. You can also preselect a face. The hole drills inward, perpendicular to the face, including side faces and tilted planes. Click again on that plane to reposition the center, or use **Reselect Face** to choose a different face. When editing an existing hole, reselect from its original source body.

Enter **Diameter** and choose **Through All** or **Distance**. Distance is measured from the selected face and produces a flat bottom. **Face U/V** specifies coordinates relative to the source body's placement origin projected onto the face; the colored U/V marks show the directions. Clicked positions snap to 1 mm by default; adjust the spacing or disable snapping. Numeric inputs always retain their exact values.

Choose **Hole type → Simple, Counterbore, Countersink or Threaded**:

- **Counterbore** adds **Recess diameter** and **Recess depth**. For example, a 6 mm hole with a 12 mm recess diameter and 4 mm recess depth has a 12 mm wide cylindrical entrance extending 4 mm into the face.
- **Countersink** adds **Sink diameter** and **Sink angle**. The angle is the full included cone angle, defaulting to 90°. A 6 mm hole with a 12 mm entrance and a 90° angle has a 3 mm deep conical recess. The panel shows the calculated recess depth.

Both support Through All and Distance. **Total depth** is measured from the selected face to the hole bottom, including the recess. The entrance diameter must exceed the hole diameter; for Distance, total depth must exceed recess depth. With Through All, a large recess can break through a thin body; inspect the preview. Two yellow rings mark the hole and entrance diameters.

**Threaded** offers Metric coarse/fine standards, **Size × pitch** (for example M6 × 1.0), and right/left handedness, with class 6H. Designations and tap-drill diameters come from the installed FreeCAD catalog. Choose Through All or Distance for the hole, then Full hole depth or a separate Thread depth. A separate thread depth must not exceed the hole depth.

- **Lightweight (default)** stores a cylindrical tap-drill hole and thread designation, handedness and depth. It does not contain helical thread geometry.
- **Model thread** creates real helical geometry with FreeCAD's Hole engine, including in STL/STEP exports. For example, an 8 mm hole with a 4 mm thread depth threads the entrance-side portion. Modeled depth is limited to 1–50 pitches to bound calculation cost. For longer holes, shorten the threaded portion or use lightweight mode.

Try **H → click a face → Hole type: Threaded → M6 × 1.0**, then enable **Model thread** to see actual threads and confirm. External threads, inch/pipe threads, combined threaded recesses and custom modeling clearance are not supported yet.

Drag the **Hole / Edit Hole** title bar to move the panel, including to the left edge. Its position is remembered. Click the title or arrow to collapse it to a small header; the preview and viewport position picking remain active, and expanding preserves all inputs. Right-click the title and choose **Restore Default Position on Right** to reset its placement. The panel stays within the working area when the window is resized.

Preview before confirming. Cancel or Esc restores visibility and selection; Ctrl+Z undoes the operation. Double-click the hole's history entry to edit its dimensions, position or extent. If a hole is the body's final operation, double-click that body in the browser or choose **Edit Hole…** from its context menu. Editing preserves a moved or rotated result's placement. Through depth automatically follows subsequent source thickness changes. Source edits during a preview require reselecting the face before confirming; topology changes that remove the reference face may also require reselection.

Existing face-based holes can be edited and switched between all four types on the same feature. Plain holes saved by previous versions remain readable and editable. Hole types, recess dimensions and thread settings support save/reopen and Undo/Redo.

The tool supports planar solid faces. Curved faces and STL meshes are not included. Old global-Z holes retain their original implementation and are not migrated automatically. Saved face-based holes require FluxCAD's `model_hole.py`, `model_thread.py` and their dependencies for parametric recomputation; start FluxCAD before opening the FCStd file. Export STEP or STL when sharing only the finished geometry.

## Mirror using a selected face or construction plane

Select a body and choose **Solid → Create → Mirror**. Choose **Mirror plane → Selected Face / Plane**, then click a planar model face or select a construction plane in the browser. A tilted plane is supported. You can also select a body followed by a reference face/plane with Ctrl before starting. Starting with a single body face selected mirrors that body across that face.

**Plane Offset** moves the mirror plane perpendicular to the selected face. Zero uses the face itself; positive values follow the orange arrow and negative values go the other way. A top face at Z=10 mm with a +2 mm offset gives a mirror plane at Z=12 mm. The reflected body moves twice as far as the plane. Numeric input supports six decimal places without grid rounding. The orange outline is a visual guide; reflection uses the infinite plane, including beyond the selected face or outline.

The source and mirrored result remain separate bodies. Moving or rotating the reference, or changing a construction plane's angle/distance, updates the mirror. Changing a construction plane's display size does not affect it. The reference body is not copied or consumed. Use Combine afterward if you need a joined body.

Double-click the mirrored body or its history entry, or choose **Edit Mirror Plane…** in the browser, to change its plane and offset. **Reference Plane** lets you reselect the face. Subsequent movement/rotation of the mirrored result is preserved. Edits that invalidate a downstream solid roll back. If the reference changes while the panel is open, reselect it before confirming.

World XY/XZ/YZ planes and their numeric positions remain available, including for older mirrors. Switching to a world plane removes the geometry reference. Cancel/Esc restores the display and selection; Confirm supports Undo/Redo without changing the camera. Drag the panel header to either edge, click to fold, or right-click to reset its position.

References must be planar faces or construction planes, not curved faces, edges or meshes. The mirror itself and its descendants cannot be referenced. Deleted or renumbered reference faces require reselection. Linked mirrors use `model_mirror.py`: **start FluxCAD before opening saved FCStd files**. World-plane mirrors remain native FreeCAD features. **Mirror-plane-demo.FCStd** shows a bracket mirrored across a linked construction plane tilted by 20°.

## Construction axes

Choose **Solid → Construct** and one of these commands:

- **Axis Through Cylinder / Cone**: click a cylindrical or conical side face. Inner hole walls and partial cylindrical/conical faces are supported.
- **Axis Through Two Points**: click two solid vertices or sketch endpoints in order. Points may belong to different objects. The positive direction runs from Point 1 to Point 2; coincident points are rejected. You can also preselect both vertices with Ctrl before starting.

The orange line and arrow preview the axis. Use **Reverse Axis Direction** if needed, then confirm. A center axis follows the surface's native direction, which is not necessarily world +Z. **Display Length** changes only the visible line: Revolve and Circular Pattern use its infinite axis and do not move when this length changes.

Axes appear in the browser's **Construction** group. In Revolve or Circular Pattern, choose **Axis Type → Edge / Cylinder / Axis**, then click the axis line or select its browser entry. Source movement, rotation and dimension changes update the axis and linked operations. Double-click the axis in the browser or history to edit its references, display length and direction.

The panel moves to either window edge, folds and scrolls without changing the camera or zoom. Cancel/Esc discards the preview; confirmation supports Ctrl+Z. Missing references clear the stale axis geometry; reselect them from its editor to repair it.

Center axes require analytic cylinders or cones, not spheres, toruses, freeform surfaces or meshes. Two-point axes use vertices/endpoints rather than circle centers, arbitrary edge points or typed coordinates. An axis cannot directly host a sketch.

Recomputation requires `model_construction_axis.py` and its dependencies: start FluxCAD before opening saved FCStd files. **Construction-axes-demo.FCStd** contains a six-instance circular pattern around a cylinder axis and a 270° revolve around a two-point axis.

## Revolve and circular pattern axes

Select a closed sketch/profile and choose **Create → Revolve**, or select a solid and choose **Create → Pattern → Circular Pattern**. In **Axis Type**, choose:

- **World Axis**: choose X, Y or Z and enter the axis origin in world coordinates.
- **Edge / Cylinder / Axis**: click a straight model/sketch edge, cylindrical side face or construction axis in the viewport. Construction axes can also be selected in the browser. Angled edges and cylindrical hole walls are supported. Use **Reference Axis** to reselect; the original source is temporarily shown during picking.
- **Direction Vector**: enter direction X/Y/Z and origin X/Y/Z. Direction (1,1,0) defines a 45° axis in XY. The vector is normalized; a zero vector is invalid. Origin coordinates are world millimetres with six decimal places.

The green arrow shows the chosen axis direction. Set the angle and forward/reverse direction, preview, then Confirm. Revolve creates a new body. Circular patterns contain 2–200 unfused instances including the original: 360° uses equal spacing around the circle without duplicating its end, while partial angles include both ends.

Edge/cylinder/construction axes remain linked to their reference, following geometry and existing parent-container placements. World/numeric axes stay fixed. Deleted or substantially renumbered edges/faces require reselection from history. Changing a reference while the panel is open also requires reselection. Arcs, planes, meshes and circular dependencies on this result or its later features are unsupported. For a cone, first create an **Axis Through Cylinder / Cone**, then select that axis.

Double-click history to change the axis, angle or count. Moved result placement is retained. Cancel/Esc restores visibility and selection, Confirm makes one undoable operation, and the camera is unchanged. Drag the panel title to either edge, click it to fold, or right-click to restore its default position. This movable panel also serves rectangular patterns, mirrors, shells, lofts, sweeps and offset planes.

Linked geometry axes require `model_axis.py` and its dependencies: **start FluxCAD before opening their saved FCStd files**. World/numeric axes use native FreeCAD properties and can recompute without FluxCAD. Export STEP/STL to share finished geometry.

## Rectangular patterns

Select a solid body and choose **Solid → Create → Pattern → Rectangular Pattern**. Set **Axis 1**, **Quantity 1** and its distance. Turn **Direction 2 → On** to add a different world axis with its own quantity and distance. For example, X with 3 instances at 10 mm and Y with 4 instances at 15 mm makes a 3×4 grid of 12 placements, including the original. XZ and YZ grids are also supported. Each active direction requires at least 2 instances; the product of the quantities is limited to 200. Negative distances reverse that direction.

**Distance Type → Spacing** measures between adjacent instance origins. **Extent** measures from the first to the last origin, excluding the body's own size. An extent of 30 mm with 4 instances places them at 0, 10, 20 and 30 mm; with 6 instances it places them at 0, 6, 12, 18, 24 and 30 mm. Quantity edits keep both endpoints in Extent mode. Switching the distance type converts the distances using the current quantities.

The preview updates without changing the model or camera. Cancel/Esc restores visibility and selection; Confirm creates one undoable operation. Double-click its history entry to edit both directions, the distance type and quantities, preserving any moved or rotated pattern placement. Turning Direction 2 off returns to a single row; toggling it in the open panel retains its pending inputs. Older one-direction patterns open in Spacing mode and can be upgraded by editing.

The pattern remains one browser item with separate, unfused copies that follow the source body's dimensions. The native FreeCAD array and expressions survive saving and reopening; source dimensions and quantities can also be recomputed in standard FreeCAD without loading FluxCAD. Independently moving copies, three-direction grids, arbitrary angled axes and patterns of individual features such as holes are not included yet.

## STL meshes

Import or open an STL, then select it in the viewport or under **Meshes** in the browser. Ctrl-click selects multiple meshes; the eye toggles visibility. The **Mesh** tab provides:

- **Move** (M): drag with 1 mm snapping by default, or enter exact placement coordinates or translation distances. Numeric entries bypass snapping.
- **Rotate Mesh**: enter an angle about a world X, Y or Z axis. Use the selection center, world origin or a custom pivot.
- **Resize Mesh**: enter a scale factor or target X/Y/Z bounding size. Unlock proportions to resize each axis independently. Double-clicking a mesh in the browser also opens this panel.
- **Separate Parts**: preview disconnected parts within one mesh, then create independently selectable meshes.
- **Plane Cut**: choose XY, YZ or XZ and a world coordinate. Keep either side or create both sides as separate meshes. Closed sources default to capped cuts; holes in hollow sections are preserved. Open meshes can be cut without caps.
- **Measure**: inspect bounding dimensions and triangle count. **Export** writes the selected transformed meshes to STL. FCStd saves the editable document.

Size, rotation, separation and cut operations have a preview, Cancel and single-step Undo. Dimensions refer to world-axis bounds. Multiple selected meshes transform together around a shared pivot. Separation and cutting operate on one source mesh at a time and create independent result meshes, retaining the hidden original. Later source changes do not update the results. Select individual results to export them separately.

Transforms and separation preserve triangles; plane cuts split boundary triangles and optionally add cap triangles without converting the entire mesh to a solid. If a complex or invalid boundary cannot be capped, the source is retained unchanged and an error is shown; move the plane or disable capping. Arbitrarily angled cutting planes, mesh holes, joining, vertex editing and solid conversion are not included yet. STL has no unit metadata; check imported dimensions before resizing.

## Components and joints

**Solid → Assemble** provides Create Components, Duplicate Component, Ground / Unground, Rigid Joint, Revolute Joint, Slider Joint and Release Joint. These are **as-built joints**: arrange parts using Move / Copy or Align before connecting them.

1. Select source bodies, open **Create Components**, check the desired bodies and optionally set a name and grounding. Confirm creates one component per body. Original bodies are hidden by default and remain editable through the browser/history.
2. Use **Duplicate Component** for additional instances sharing the original geometry. Source dimension edits update the instances, while placements remain independent. Moving the source or its parent container does not move existing instances. Use M to drag or enter coordinates for free components, and Move / Copy for numeric rotation. The ordinary Copy option creates an independent body snapshot; use Duplicate Component for associative copies.
3. Use **Ground / Unground** to fix a reference component. Double-click a component to edit its name and grounding.
4. Ctrl-select the moving component first and anchor second, then choose **Rigid Joint**, **Revolute Joint** or **Slider Joint**, or use the panel's two selection lists. A rigid joint preserves their current relative pose and follows anchor movement and rotation.
5. A revolute joint adds an angle field, slider and optional minimum/maximum motion limits. Zero is the original connected pose. Choose X/Y/Z or a custom direction and origin in the **anchor's local frame**. **Capture axis from edge / cylinder** also accepts a straight edge or cylindrical side face in the viewport.
6. A slider joint translates a component along an axis while preserving its relative orientation. Enter **Distance in mm** or use the slider; **Limit travel** sets minimum and maximum distances. For example, 0–40 mm constrains travel to that range. Positive values follow the green arrow, negative values reverse it, and zero means the original connected position. Choose X/Y/Z or a custom direction in the **anchor's local frame**, or capture a straight edge/cylinder direction. Axis origin does not affect linear motion.

Double-click a browser **Joints** entry or its history item to edit it. Connected descendants follow changes through a joint tree. Preview keeps document placements and the camera unchanged until OK; Cancel/Esc restores visibility. Confirm is a single undoable transaction. Panels drag to either edge, collapse and scroll on small windows.

Grounded and joint-driven components cannot be moved directly with M. Unground, change the joint angle/distance, or use **Release Joint** to keep the current pose and free the component. Release and recreate a joint to change its endpoints. Types can be switched in the editor; changing back to Rigid uses the original zero-angle/zero-distance relative pose. Angular and linear values/limits are stored separately. Invalid references/settings appear as red browser warnings and clear stale driven geometry; repair the joint or release it to recover.

**Try it:** open `Assembly-demo.FCStd` from FluxCAD and double-click **Arm rotation** under Joints. It contains a grounded base, rigid shaft and blue arm with ±90° limits, initially at 30°.

**Linear motion sample:** open `Slider-demo.FCStd` and double-click **Carriage travel** under Joints. The blue carriage moves along the rail over 0–40 mm, initially at 15 mm. Distances accept six decimal places within ±1000000 mm. Equal minimum/maximum limits lock the travel at one value.

Previous rigid/revolute FCStd assemblies open without changes to their data schema. Distance properties are added only when a joint edit is confirmed; Cancel preserves the original data.

This first assembly implementation supports root-level, single-body components in one document, one driver per component, and acyclic mixed rigid/revolute/slider chains. Nested assemblies, closed mechanisms, simultaneous multiple constraints, joint dragging, collision/contact simulation and automatic face mating are not included. A captured edge/cylinder axis stores coordinates at capture time; recapture after shape changes when needed. Instances follow edits to their original source feature, but do not automatically switch to later features added after component creation.

Components and joints use Python proxies in `model_assembly.py`. **Start FluxCAD before opening saved FCStd assemblies.** STEP/STL export transfers selected component geometry at its current position; joint definitions remain in FCStd only.

## Pattern on Path

Choose **Solid → Create → Pattern → Pattern on Path**. Select a body and a sketch or wire containing one connected path, either before opening the command or in its panel.

- **Quantity** includes the original and accepts 2–200 instances.
- **Entire Path** distributes copies over the available length. **Spacing** specifies the distance between neighbors; **Extent** specifies the distance from the first to the last. All distances follow the curve's arc length.
- **Keep Orientation** translates each copy without rotation. **Follow Tangent** rotates copies along the path. **Reverse Path Direction** traverses the path from the other end. The green preview arrow and coordinate readout identify the start.
- Closed paths using their full length omit the duplicate endpoint. Distances beyond the path and spacing that repeats the closed path's start cannot be confirmed.

The original stays in place. Copies follow the displacement from the path start, so **position the original at that start if copies should lie on the path itself**. Translating only the path does not change its relative displacements. Source body dimensions/position and path length, bends and orientation remain linked to the result.

Double-click the browser body or timeline entry to edit the source, path, quantity, distance and orientation again. A moved pattern retains its additional placement. The movable panel supports scrolling, folding, Cancel/Esc and one-step Undo/Redo; the camera and zoom stay unchanged. Deleted references clear stale geometry and can be replaced by editing the same pattern.

Lines, arcs, closed circles, B-splines and spatial wires are supported. Copies remain separate solids in one pattern item; overlapping solids are not automatically resolved or fused. A multi-solid source is copied as a group, with at most 2000 solids in the result. Branched/disconnected paths, selecting several independent bodies, individual feature patterns, gathering individual solid edges as a path and suppressing individual instances are not included.

`Path-pattern-demo.FCStd` shows 18 bodies along connected lines and arcs. This feature uses `model_path_pattern.py`; start FluxCAD before reopening its FCStd files. Finished solids can be exported to STEP/STL.

## Sketch projection, intersection and dimensions

The ribbon now exposes these native FreeCAD 1.1.3 sketch tools:

- **Project**: Open **Sketch → Create → Project / Include → Project**, then click visible edges, vertices or faces of another sketch or body. Selecting a face projects its boundary onto the active sketch plane. References follow changes to the source.
- **Intersect**: From the same submenu, select faces or edges crossing the sketch plane. For example, select the side faces of a box to obtain its section at the sketch elevation.
- Click **Select (Finish Drawing)** to stop collecting references. If a source is hidden, show it using the browser's eye icon. Projected geometry cannot be reshaped by dragging; edit its source instead.
- Select projected edges and use **Modify → Toggle Construction** to switch between reference construction geometry and defining profile geometry. After finishing the sketch, closed defining profiles can be selected and extruded. The initial construction setting follows FreeCAD's preferences.
- **Dimension**: Select a line, circle or arc and use **Create → Dimension**. Click the dimension's display position and enter its value. Press M during placement to cycle dimension types. **Create → Dimension Types** also offers explicit length/distance, horizontal distance, vertical distance, radius, diameter and angle commands.
- **Reference dimensions**: Select dimension text and use **Constraints → Toggle Driving / Reference Dimension**. Driving dimensions control geometry; reference dimensions measure it, including projected geometry. Avoid adding conflicting driving dimensions to already constrained geometry.
- **Point on Object**: In selection mode, Ctrl-click a point and a line or curve, then use **Constraints → Point on Object**. Projected edges can serve as references.

These features persist as native FreeCAD external geometry and dimensional constraints. Deleted source geometry or major changes to its edge/face topology may require repairing references. Downstream geometry depending on the current sketch cannot be referenced back into it because that creates a dependency cycle.

`Sketch-projection-demo.FCStd` contains a projected box face and its extrusion. Changing the source box length updates both. Hidden sketches in the same file demonstrate intersections and dimensions.

## Sketch mirrors, patterns and editing

While editing a sketch, finish the current drawing tool using **Select**, then select lines, circles or other geometry. Ctrl-click selects multiple elements. These commands use native FreeCAD Sketcher tools.

- **Mirror**: **Create → Mirror**. Select geometry, launch the tool, then click the reflection reference, such as a sketch axis. The task controls offer deleting originals and creating symmetry constraints.
- **Rectangular Pattern**: **Create → Pattern → Rectangular Pattern**. Enter column and row counts, then click the placement position. Three columns and two rows make six instances including the original. The last selected point is the reference. The native dialog provides equal spacing, separation constraints and cloning options.
- **Rotate / Circular Pattern**: Available under **Create → Pattern** and **Modify**. Click the center, starting direction and destination direction. Zero copies rotates the original; three copies creates three additional instances.
- **Move / Array**: **Modify → Move / Array**. Click a base point and destination. Zero copies moves the original; larger copy counts create duplicates. Additional rows enable a second array direction.
- **Copy**: **Modify → Copy**. Select geometry and select its reference point last, then launch the tool and click the destination.
- **Scale**: **Modify → Scale**. Click the center, a reference-distance point and a target-distance point. Distances of 10 mm and 20 mm give a scale factor of two. The task control can retain the original geometry.
- **Split Edge**: **Modify → Split Edge**. Click the point on an edge where it should be divided.
- **Chamfer**: **Modify → Chamfer**. Select a corner and choose the chamfer size. Preserving the corner may retain auxiliary geometry; the defining profile uses the chamfer line.
- **Rounded Rectangle**: **Create → Rectangle → Rounded Rectangle**. Set two opposite corners and the corner rounding size.
- **Arc Slot**: **Create → Slot → Arc Slot**. Set the arc center, start, end and width.

Use **Select (finish drawing)** to stop an unfinished operation, or Ctrl+Z to undo a completed change. Fully constrained geometry or constraints connecting the selection to other geometry can restrict transformations. Patterns are saved as native sketch geometry and constraints rather than separate Fusion-style pattern features.

`Sketch-transforms-demo.FCStd` contains the results of these operations. Show and edit the individual sketches from the browser.

## Distribution

Keep `Start-FluxCAD.cmd`, `Start-FluxCAD.ps1`, `FluxCAD.FCMacro`, all top-level `.py` files (including `i18n.py` and `translations_en.py`), `icons`, `templates`, the README files and `LICENSE` together. Test reports, preview images, caches, personal `config`, backups and personal models are not required. `Sample.FCStd`, `Assembly-demo.FCStd`, `Slider-demo.FCStd`, `Primitives-demo.FCStd` and `Path-pattern-demo.FCStd` are optional samples.

Recipients need a compatible FreeCAD installation, or a suitable portable FreeCAD runtime in `runtime`. Most features use native FreeCAD objects. Face-based holes, associative extrusion extents, body splits, the new Combine panel, linked geometry axes, components and joints additionally use FluxCAD Python tools; keep the module files together and open their FCStd files from FluxCAD to retain recomputation and editing.

The current workspace supports solid modeling, basic sketching, extrusions, revolutions, lofts, sweeps, patterns, mirrors, shells, planar body splits, movement, planar/coaxial alignment, native surface modeling, extension, offsets, thickening and refinement, basic component assemblies with rigid/revolute/slider joints, and native TechDraw sheets, projections, dimensions, notes and PDF/SVG export. It does not yet provide an advanced assembly solver or a sheet-metal, CAM or simulation workflow. See `README.md` for detailed feature limitations.


## Drawing workspace (TechDraw)

Choose **Design ▼ → Drawing** at the upper left. The drawing workflow uses native FreeCAD TechDraw objects linked to the source model.

1. **Sheet → New Drawing** creates an A4 or A3 landscape sheet with a title, scale factor and first-angle or third-angle projection.
2. Select source bodies, sketches or surfaces in the browser, then choose **Create → Base View** or **Projected Views**. Ctrl-click selects multiple source objects. Projected Views creates a linked front/top/right group.
3. Set the base direction, page or custom scale, hidden-line visibility and X/Y placement. Coordinates are millimetres from the lower-left of the sheet. Drag a view frame to reposition it. **Modify → Toggle View Frames** shows or hides the frames.
4. Select **edges on the drawing sheet**, then use **Dimensions** for length, horizontal, vertical, radius, diameter or angle dimensions. Ctrl-click selects two points or edges. Values reflect model dimensions and remain unchanged when the drawing magnification changes. Drag dimension text to position it; double-click to open FreeCAD's native dimension editor.
5. **Annotations → Note** adds multi-line text with numeric placement and text height. **Export → Export PDF / Export SVG** exports the current sheet.

The browser's Drawings group lists sheets, views, dimensions and notes hierarchically. Double-click a sheet to open it, or a view/note to edit its parameters. **Sheet → Sheet Settings** edits scale, projection and title-block fields. Page scale applies to views configured to use it. **Return to Design** returns to the 3D document with its camera unchanged. Sheets remain accessible from the browser or Open Drawing when bottom document tabs are hidden.

Using Toggle View Frames switches TechDraw's frame preference to Manual mode. After geometry or scale changes, dimension values update when native projection calculation finishes.

All drawing objects and links are native, with no custom Python document proxy. The template is embedded in FCStd. Standard FreeCAD can reopen the file and update its views and dimensions after model changes. Removing edges or changing topology substantially can require repairing dimension references.

Example: `samples/Drawing-demo.FCStd`. Generate PDF/SVG files using the drawing export commands. The supplied templates are original, simple layouts; they do not claim complete compliance with a drafting standard. Geometric tolerances, parts lists and replacing an existing view's source models are not yet exposed here; additional native TechDraw tools remain available in FreeCAD.

### Section views, details and centerlines

- **Create → Section View**: select a source drawing view on the sheet or in the browser. In the native task, enter an identifier such as A, choose a direction button, set the section origin X/Y/Z and use Update Now before OK. The origin uses 3D model coordinates. The base view receives the cutting line and arrows. Selecting a projection group uses its front anchor view.
- **Create → Detail View**: select a source drawing view and set the focus X/Y, radius, scale and reference letter. Drag Highlight also moves the focus. Focus coordinates are relative to the source view center, not sheet coordinates. After accepting, drag the view frame or use numeric placement.
- **Modify → View Placement and Display**: set a selected view's X/Y, caption, outline width and white face display. Coordinates are sheet millimetres, except projection-group children which use relative coordinates. Sections additionally offer cut-face display mode, geometric hatch pattern, scale and rotation.
- **Annotations → Hatch**: select a drawing face and set its pattern, scale, rotation, line weight and color. The native hatch appears under its source view in the browser; double-click it to edit.
- **Annotations → Center Marks**: select circular drawing edges to create two center strokes. For **Centerline Between Edges**, Ctrl-select two edges in the same view. **Face Centerline** uses selected drawing faces. Native task settings include orientation, extension and line style.
- **Modify → Remove Cosmetic Geometry** removes selected cosmetic edges or center-mark strokes. It leaves projected model outlines intact and supports Undo.

Double-click a section or detail to reopen its native task. Finish or cancel the current task before starting another operation. Sections and details are standard TechDraw objects linked to the source model. Hatch patterns are embedded in FCStd. Center marks are saved as cosmetic drawing lines: check their placement and recreate them if necessary after changing a circle's position or geometry. Major topology changes can require repairing hatch, dimension and centerline references.

Use the commands above to create sections, enlarged details, centerlines and hatching. The drawing-detail development sample is not included in this initial package. State a detail's magnification in its caption when it differs from the sheet scale.

The exported example PDF has been visually checked. FreeCAD 1.1.3's native PDF exporter can emit empty color-setting (SCN) operations, which produce Poppler parser warnings. The tested drawing geometry and text render successfully; strict PDF conformance remains a known limitation.
