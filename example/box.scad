// Example model for openscad.mk: a small box with a press-fit lid.
// Every printed part is modelled in print orientation, sitting on z = 0.

part = "assembly"; // box | lid | assembly
cut = false;       // slice the assembly open to show the fit

size = [40, 30, 20];
wall = 2;
lid_h = 3;
lip = 2;
fit = 0.2; // clearance between the lid's lip and the box

module box() {
    difference() {
        cube(size);
        translate([wall, wall, wall])
            cube([size.x - 2 * wall, size.y - 2 * wall, size.z]);
    }
}

// Printed upside down: the flat top is on the bed and the lip points up.
module lid() {
    cube([size.x, size.y, lid_h]);
    translate([wall + fit, wall + fit, lid_h])
        cube([size.x - 2 * (wall + fit), size.y - 2 * (wall + fit), lip]);
}

module assembly() {
    color("SteelBlue") box();
    color("Orange")
        translate([0, size.y, size.z + lid_h])
            rotate([180, 0, 0])
                lid();
}

if (part == "box") box();
else if (part == "lid") lid();
else difference() {
    assembly();
    if (cut) translate([-1, -1, -1]) cube([size.x + 2, size.y / 2 + 1, size.z + lid_h + 2]);
}
