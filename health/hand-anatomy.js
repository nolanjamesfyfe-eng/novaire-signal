const DISTAL_HAND_PATTERN=/(?:^|_)(?:left|right)_(?:capitate|hamate|lunate|pisiform|scaphoid|trapezium|trapezoid|triquetrum|first_metacarpal_bone|second_metacarpal_bone|third_metacarpal_bone|fourth_metacarpal_bone|fifth_metacarpal_bone)$|(?:distal|middle|proximal)_phalanx_of_(?:left|right)_(?:thumb|index_finger|middle_finger|ring_finger|little_finger)/i;

const DIGITS=[
  {id:'thumb',ordinal:'first',segments:['proximal','distal'],radius:5.4},
  {id:'index_finger',ordinal:'second',segments:['proximal','middle','distal'],radius:4.8},
  {id:'middle_finger',ordinal:'third',segments:['proximal','middle','distal'],radius:5.0},
  {id:'ring_finger',ordinal:'fourth',segments:['proximal','middle','distal'],radius:4.6},
  {id:'little_finger',ordinal:'fifth',segments:['proximal','middle','distal'],radius:4.1}
];
const CARPALS=['scaphoid','lunate','triquetrum','pisiform','trapezium','trapezoid','capitate','hamate'];

export function isDefectiveDistalHandNode(name=''){return DISTAL_HAND_PATTERN.test(String(name).toLowerCase())}
function displayName(name){return name.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase())}

// Closed, gently waisted long-bone profile. Every bone is built between shared
// joint coordinates; there is no reuse of the exploded source-hand centres.
function boneGeometry(THREE,length,radius,quality=20){
  const p=[[0,-.5],[.82,-.5],[1.06,-.47],[1.13,-.42],[.78,-.31],[.61,-.12],[.59,.12],[.77,.31],[1.10,.42],[1.02,.47],[.78,.5],[0,.5]]
    .map(([r,y])=>new THREE.Vector2(r*radius,y*length));
  const geometry=new THREE.LatheGeometry(p,quality,0,Math.PI*2);geometry.computeVertexNormals();return geometry;
}
function orientedBone(THREE,a,b,radius,material,name,key){
  const direction=b.clone().sub(a),length=direction.length(),mesh=new THREE.Mesh(boneGeometry(THREE,length,radius),material());
  mesh.position.copy(a).lerp(b,.5);mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),direction.normalize());mesh.name=name;
  mesh.userData={key,layer:'bone',replacementHand:true,anatomicalName:displayName(name),jointA:a.toArray(),jointB:b.toArray()};return mesh;
}
function carpalGeometry(THREE,radius){const g=new THREE.SphereGeometry(radius,20,14);g.scale(1.16,.72,.94);return g}
function addCarpal(THREE,group,point,radius,material,name,key){const mesh=new THREE.Mesh(carpalGeometry(THREE,radius),material());mesh.position.copy(point);mesh.rotation.set(.12,.08,.18);mesh.name=name;mesh.userData={key,layer:'bone',replacementHand:true,anatomicalName:displayName(name)};group.add(mesh);return mesh}
function localPoint(frame,x,y,z){return frame.wrist.clone().addScaledVector(frame.across,x).addScaledVector(frame.depth,y).addScaledVector(frame.proximal,z)}

function meshPoints(THREE,node){
  const position=node.geometry?.attributes?.position;if(!position)return[];node.updateWorldMatrix(true,false);
  return Array.from({length:position.count},(_,i)=>new THREE.Vector3().fromBufferAttribute(position,i).applyMatrix4(node.matrixWorld));
}
function capCenter(THREE,points,axis,distal=true){
  const ordered=points.map(point=>({point,dot:point.dot(axis)})).sort((a,b)=>a.dot-b.dot),count=Math.max(12,Math.ceil(ordered.length*.08)),cap=distal?ordered.slice(0,count):ordered.slice(-count),center=new THREE.Vector3();
  for(const {point} of cap)center.add(point);return center.multiplyScalar(1/cap.length);
}
function wristFrame(THREE,sourceNodes,side){
  const named=kind=>sourceNodes.find(node=>new RegExp(`(?:^|_)${side}_${kind}(?:_|$)`,'i').test(node.name||''));
  const radius=named('radius'),ulna=named('ulna');if(!radius||!ulna)throw new Error(`Missing ${side} radius/ulna for replacement hand frame`);
  const rp=meshPoints(THREE,radius),up=meshPoints(THREE,ulna),all=[...rp,...up],vertical=new THREE.Vector3(0,0,1);
  const low=capCenter(THREE,all,vertical,true),high=capCenter(THREE,all,vertical,false),proximal=high.clone().sub(low).normalize();
  const rd=capCenter(THREE,rp,proximal,true),ud=capCenter(THREE,up,proximal,true),wrist=rd.clone().add(ud).multiplyScalar(.5),across=rd.clone().sub(ud).normalize();
  if(side==='right')across.negate();
  const depth=new THREE.Vector3().crossVectors(proximal,across).normalize();
  return{wrist,across,depth,proximal,source:{radiusDistal:rd.toArray(),ulnaDistal:ud.toArray(),distalSeparation:rd.distanceTo(ud),axis:proximal.toArray()}};
}

export function buildReplacementHands({THREE,sourceNodes,material,keyForBone,registerStructure,registerPart}){
  const root=new THREE.Group();root.name='intact-procedural-hands';const sides={};let serial=0;
  for(const side of ['left','right']){
    const group=new THREE.Group();group.name=`${side}-intact-hand`;root.add(group);
    const frame=wristFrame(THREE,sourceNodes,side),wrist=frame.wrist;

    // Compact two-row carpus rooted immediately below the source radius/ulna.
    const cp={
      scaphoid:[13,0,-6.5],lunate:[3,0,-6.2],triquetrum:[-7,0,-6.5],pisiform:[-10,-6,-9],
      trapezium:[17,-1,-16],trapezoid:[8,0,-16],capitate:[0,0,-17],hamate:[-10,0,-17]
    };
    const carpalPoints={};
    for(const carpal of CARPALS){
      const point=localPoint(frame,...cp[carpal]);carpalPoints[carpal]=point;
      const name=`${side}_${carpal}`,key=keyForBone(name,`hand-${serial++}`);registerStructure(key,name);
      registerPart(addCarpal(THREE,group,point,carpal==='pisiform'?4.1:5.3,material,name,key));
    }
    // Shared articulation coordinates. Values are offsets from the source wrist;
    // all four fingers run distally together while the thumb fans naturally.
    const rays={
      thumb:[[18,-1,-13],[29,-2,-27],[39,-3,-39],[47,-2,-50]],
      index:[[8,0,-14],[13,0,-53],[15,-1,-82],[16,-2,-104],[17,-3,-120]],
      middle:[[0,0,-15],[1,0,-57],[2,-1,-90],[3,-2,-115],[4,-3,-133]],
      ring:[[-8,0,-15],[-10,0,-54],[-12,-1,-84],[-13,-2,-107],[-14,-3,-123]],
      little:[[-14,0,-14],[-20,0,-48],[-24,-1,-73],[-27,-2,-92],[-29,-3,-106]]
    };
    const anchors={thumb:'trapezium',index_finger:'trapezoid',middle_finger:'capitate',ring_finger:'hamate',little_finger:'hamate'};
    const digitMetrics=[];let maximumJointGap=0;
    for(const digit of DIGITS){
      const raw=rays[digit.id==='index_finger'?'index':digit.id==='middle_finger'?'middle':digit.id==='ring_finger'?'ring':digit.id==='little_finger'?'little':'thumb'];
      const joints=raw.map(v=>localPoint(frame,...v));joints[0]=carpalPoints[anchors[digit.id]].clone();
      const names=[`${side}_${digit.ordinal}_metacarpal_bone`,...digit.segments.map(segment=>`${segment}_phalanx_of_${side}_${digit.id}`)];
      names.forEach((name,i)=>{
        const key=keyForBone(name,`hand-${serial++}`);registerStructure(key,name);
        const radius=digit.radius*(i===0?1.04:i===1?1:i===2?.82:.68);
        const bone=orientedBone(THREE,joints[i],joints[i+1],radius,material,name,key);group.add(bone);registerPart(bone);
        if(i>0)maximumJointGap=Math.max(maximumJointGap,new THREE.Vector3(...group.children.at(-2).userData.jointB).distanceTo(joints[i]));
      });
      digitMetrics.push({digit:digit.id,segments:names.length,root:joints[0].toArray(),tip:joints.at(-1).toArray(),jointGaps:new Array(names.length-1).fill(0)});
    }
    sides[side]={carpals:8,digits:digitMetrics,wristCenter:wrist.toArray(),frame:{across:frame.across.toArray(),depth:frame.depth.toArray(),proximal:frame.proximal.toArray()},source:frame.source,meshes:group.children.length,maximumJointGap};
  }
  root.userData.handMetrics={version:2,source:'shared-joint procedural anatomical reconstruction',sides,totalMeshes:root.children.reduce((n,g)=>n+g.children.length,0)};
  return root;
}
