// Indoor rubber propeller mount. Units mm. OpenSCAD source. 2026-11-01
$fn=64;
variant="V";   // "V" or "plate"
insertion=10; // 5 or 10 mm
bore=10.2; wall=0.8; shaft_d=0.8;
axis_offset=12; left_thrust_deg=2;
module beam(a,b,d=1.2) {hull(){translate(a)sphere(d=d);translate(b)sphere(d=d);}}
module mount(){
 difference(){
 union(){
   // sleeve
   difference(){cylinder(h=insertion,d=bore+2*wall); translate([0,0,-0.1]) cylinder(h=insertion+0.2,d=bore);}
   // bearing tube with local 2 degree thrust (about y), axis is nearly z
   translate([axis_offset,0,1.5]) rotate([0,left_thrust_deg,0])
      difference(){cylinder(h=5,d=2.8,center=true);cylinder(h=5.2,d=0.95,center=true);}
   if(variant=="plate") {
     // beam joining sleeve and front bearing, 2 mm wide, 3 mm thick axially
     translate([5.15,-1.0,0.0])cube([7.1,2.0,3.0]);
   } else {
     // two diagonal rails form a triangle in the XZ plane
     beam([6.1,0,0.65],[axis_offset,0,1.5],1.65);
     beam([6.1,0,insertion-0.65],[axis_offset,0,1.5],1.65);
     // small transverse tie around bearing
   }
 }
 // final shaft hole also through connections
 translate([axis_offset,0,1.5]) rotate([0,left_thrust_deg,0]) cylinder(h=8,d=0.95,center=true);
 }
}
mount();
