// ============================================================
//  CROSSY ROAD  —  Three.js 3D Implementation
// ============================================================

(function () {
  'use strict';

  // ─── Constants ───────────────────────────────────────────
  const TILE_SIZE      = 1;          // world units per grid cell
  const LANE_WIDTH     = TILE_SIZE;
  const GRID_COLS      = 51;         // wide enough to fill screen edge-to-edge
  const HALF_COLS      = Math.floor(GRID_COLS / 2);
  const VISIBLE_ROWS   = 20;         // how many rows to keep rendered ahead/behind
  const GENERATE_AHEAD = 15;         // generate this many rows ahead of player

  const CAM_OFFSET  = new THREE.Vector3(0, 9, 7);
  const CAM_LOOK_AHEAD = 2;          // look slightly ahead of player

  const HOP_DURATION  = 0.18;        // seconds per hop
  const HOP_HEIGHT    = 0.55;

  const LANE_TYPES = { GRASS: 'grass', ROAD: 'road', RIVER: 'river' };

  const COLORS = {
    // Grass — bright lime green like the reference
    grass:        [0x74b944, 0x6aad3a, 0x7dc94e],
    grassDark:    [0x5a9932, 0x518c2d, 0x62a63a],
    // Road — blue-grey like the reference (not dark charcoal)
    road:         0x8899aa,
    roadDark:     0x7788999,
    roadLine:     0xffffff,
    sidewalk:     0xaabbcc,
    // River — bright cyan-blue like the reference
    water:        0x40c0e0,
    waterDark:    0x30acd0,
    // Logs — flat brown planks
    log:          0x9b6b3a,
    logTop:       0xb87c45,
    logSide:      0x7a4f26,
    // Car body colors — bright saturated like reference
    carColors:    [0xe8d44d, 0x5bc95b, 0xe05252, 0x9b6bcc, 0xe87722, 0x4a9de8, 0xff6699],
    carCabin:     0xeeeeff,   // white/light cabin on all cars
    // Truck colors — cab is a bright color, cargo is always white
    truckCabColors: [0xe05252, 0x4a9de8, 0x5bc95b, 0xe87722],
    truckCargo:   0xeeeeff,
    // Chicken
    chickenBody:  0xffffff,
    chickenBeak:  0xf39c12,
    chickenComb:  0xe74c3c,
    chickenEye:   0x111111,
    chickenFeet:  0xf39c12,
    chickenWing:  0xeeeeee,
    shadow:       0x000000,
    // Sky / fog — match road blue-grey tone
    sky:          0x99aabb,
    fogColor:     0x99aabb,
    // Trees — blocky bright green like reference, brown trunk
    treeCube:     0x7dc93a,
    treeCubeDark: 0x5fa828,
    treeTrunk:    0x8B5a2a,
    bush:         0x7dc93a,
  };

  // ─── State ───────────────────────────────────────────────
  let scene, camera, renderer;
  let clock;
  let gameState = 'start';   // 'start' | 'playing' | 'paused' | 'dead' | 'gameover'
  let prevGameState = 'playing'; // state before pause

  let player;
  let score      = 0;
  let bestScore  = 0;
  let maxRow     = 0;        // furthest row ever reached

  let lanes      = [];       // array of lane descriptors
  let laneObjects = [];      // THREE.Group per lane row
  let obstacles  = [];       // moving objects

  let keysDown   = {};
  let inputQueue = [];       // queued hop directions

  let playerState = {
    row:        0,
    col:        0,
    worldX:     0,
    worldZ:     0,
    hopping:    false,
    hopT:       0,
    hopFrom:    null,
    hopTo:      null,
    hopDir:     null,
    dead:       false,
    deathAnim:  0,
    onLog:      null,   // reference to log obstacle player is riding
    logOffsetX: 0,      // player X offset from log centre at time of landing
    invincible: 0,
  };

  // DOM refs
  const canvas        = document.getElementById('game-canvas');
  const scoreDisplay  = document.getElementById('score-display');
  const startScreen   = document.getElementById('start-screen');
  const gameoverScreen= document.getElementById('gameover-screen');
  const finalScoreEl  = document.getElementById('final-score');
  const bestScoreEl   = document.getElementById('best-score');
  const startBtn      = document.getElementById('start-btn');
  const restartBtn    = document.getElementById('restart-btn');
  const controlsHint  = document.getElementById('controls-hint');

  // ─── Init ────────────────────────────────────────────────
  function init() {
    // Renderer
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
    renderer.setClearColor(COLORS.sky);

    // Scene
    scene = new THREE.Scene();
    scene.fog = new THREE.Fog(COLORS.fogColor, 18, 45);
    scene.background = new THREE.Color(COLORS.sky);

    // Camera — isometric-ish fixed-angle following camera
    camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
    resetCamera(0);

    // Clock
    clock = new THREE.Clock();

    // Lighting
    setupLighting();

    // Events
    window.addEventListener('resize', onResize);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup',   onKeyUp);
    startBtn.addEventListener('click',   startGame);
    restartBtn.addEventListener('click', restartGame);

    // Start render loop immediately (show background while on start screen)
    buildInitialWorld();
    buildPlayer();
    animate();
  }

  // ─── Lighting ────────────────────────────────────────────
  function setupLighting() {
    // Ambient — reduced intensity for less washed-out look
    const ambient = new THREE.AmbientLight(0xddeeff, 0.45);
    scene.add(ambient);

    // Main sun directional light — dimmer, cooler tone
    const sun = new THREE.DirectionalLight(0xfff0cc, 0.75);
    sun.position.set(8, 16, 8);
    sun.castShadow = true;
    sun.shadow.mapSize.width  = 2048;
    sun.shadow.mapSize.height = 2048;
    sun.shadow.camera.left   = -20;
    sun.shadow.camera.right  =  20;
    sun.shadow.camera.top    =  20;
    sun.shadow.camera.bottom = -20;
    sun.shadow.camera.near   = 0.5;
    sun.shadow.camera.far    = 80;
    sun.shadow.bias = -0.001;
    scene.add(sun);

    // Soft fill from opposite side — kept subtle
    const fill = new THREE.DirectionalLight(0x8899cc, 0.20);
    fill.position.set(-6, 8, -4);
    scene.add(fill);
  }

  // ─── Camera ──────────────────────────────────────────────
  function resetCamera(targetZ) {
    camera.position.set(0, CAM_OFFSET.y, targetZ + CAM_OFFSET.z);
    camera.lookAt(0, 0, targetZ - CAM_LOOK_AHEAD);
  }

  function updateCamera(dt) {
    // Camera only follows the player forward (Z axis). X is always fixed at 0
    // so the view never tilts or shifts when the chicken moves sideways or turns.
    const targetZ    = playerState.worldZ - 3;
    const camTargetZ = targetZ + CAM_OFFSET.z;

    const speed = 6;
    camera.position.x  = 0;                        // always centred
    camera.position.y  = CAM_OFFSET.y;             // fixed height
    camera.position.z += (camTargetZ - camera.position.z) * Math.min(1, speed * dt);
    camera.lookAt(0, 0, targetZ - CAM_LOOK_AHEAD); // always look down the centre
  }

  // ─── World Generation ────────────────────────────────────
  function buildInitialWorld() {
    // Row 0 is starting grass row; negative rows are behind start
    for (let r = -4; r <= GENERATE_AHEAD; r++) {
      generateLane(r);
    }
  }

  function generateLane(row) {
    if (lanes[row + 1000] !== undefined) return; // already generated

    let type;
    if (row <= 0) {
      type = LANE_TYPES.GRASS;
    } else {
      // Weight probabilities
      const prev = row > 1 ? lanes[(row - 1) + 1000]?.type : LANE_TYPES.GRASS;
      const r    = Math.random();
      // Avoid 3+ rivers in a row (too hard), avoid same type too many times
      const prevPrev = row > 2 ? lanes[(row - 2) + 1000]?.type : null;
      if (prev === LANE_TYPES.RIVER && prevPrev === LANE_TYPES.RIVER) {
        type = r < 0.55 ? LANE_TYPES.ROAD : LANE_TYPES.GRASS;
      } else if (prev === LANE_TYPES.ROAD) {
        type = r < 0.4 ? LANE_TYPES.ROAD : (r < 0.75 ? LANE_TYPES.GRASS : LANE_TYPES.RIVER);
      } else {
        type = r < 0.35 ? LANE_TYPES.ROAD : (r < 0.65 ? LANE_TYPES.GRASS : LANE_TYPES.RIVER);
      }
    }

    const laneData = buildLaneData(row, type);
    lanes[row + 1000] = laneData;

    const group = buildLaneMesh(laneData);
    laneObjects[row + 1000] = group;
    scene.add(group);
  }

  function buildLaneData(row, type) {
    const data = { row, type, obstacles: [] };

    if (type === LANE_TYPES.ROAD) {
      data.direction = Math.random() < 0.5 ? 1 : -1;
      // Slowed down: was 2.5–6.0, now 1.2–3.0
      data.speed     = 1.2 + Math.random() * 1.8 + row * 0.015;
      const count = 4 + Math.floor(Math.random() * 4);
      const spacing = GRID_COLS / count;
      for (let i = 0; i < count; i++) {
        const isTruck = Math.random() < 0.25;
        data.obstacles.push({
          type:  isTruck ? 'truck' : 'car',
          col:   -HALF_COLS + i * spacing + (Math.random() - 0.5) * spacing * 0.5,
          row,
          speed: data.speed * data.direction,
          width: isTruck ? 2.4 : 1.2,
          mesh:  null,
        });
      }
    } else if (type === LANE_TYPES.RIVER) {
      data.direction = Math.random() < 0.5 ? 1 : -1;
      // Slowed down: was 1.5–3.5, now 0.7–1.6
      data.speed     = 0.7 + Math.random() * 0.9;
      const count = 4 + Math.floor(Math.random() * 4);
      const spacing = GRID_COLS / count;
      for (let i = 0; i < count; i++) {
        const logLen = 2.2 + Math.random() * 1.8;
        data.obstacles.push({
          type:  'log',
          col:   -HALF_COLS + i * spacing + (Math.random() - 0.5) * spacing * 0.5,
          row,
          speed: data.speed * data.direction,
          width: logLen,
          mesh:  null,
        });
      }
    } else {
      // Grass — possibly add trees/bushes
      data.trees = [];
      if (row !== 0) {
        const treeChance = 0.5;
        for (let c = -HALF_COLS; c <= HALF_COLS; c++) {
          if (Math.random() < treeChance * 0.22) {
            data.trees.push(c);
          }
        }
      }
    }

    return data;
  }

  function buildLaneMesh(data) {
    const group = new THREE.Group();
    const z     = -data.row * LANE_WIDTH;

    if (data.type === LANE_TYPES.GRASS) {
      buildGrassLane(group, data, z);
    } else if (data.type === LANE_TYPES.ROAD) {
      buildRoadLane(group, data, z);
    } else if (data.type === LANE_TYPES.RIVER) {
      buildRiverLane(group, data, z);
    }

    return group;
  }

  // ─── Lane Builders ───────────────────────────────────────
  function buildGrassLane(group, data, z) {
    const colorArr  = COLORS.grass;
    const baseColor = colorArr[Math.abs(data.row) % colorArr.length];

    const geo  = new THREE.BoxGeometry(GRID_COLS, 0.2, LANE_WIDTH);
    const mat  = new THREE.MeshLambertMaterial({ color: baseColor });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(0, -0.1, z);
    mesh.receiveShadow = true;
    group.add(mesh);

    // Trees / bushes
    if (data.trees) {
      data.trees.forEach(col => {
        const bush = Math.random() < 0.25;
        const obj  = bush ? makeBush() : makeTree();
        obj.position.set(col * TILE_SIZE, 0, z);
        group.add(obj);
        if (!data.blockedCols) data.blockedCols = new Set();
        data.blockedCols.add(col);
      });
    }
  }

  function buildRoadLane(group, data, z) {
    // Road surface — blue-grey
    const roadGeo = new THREE.BoxGeometry(GRID_COLS, 0.15, LANE_WIDTH);
    const roadMat = new THREE.MeshLambertMaterial({ color: COLORS.road });
    const road    = new THREE.Mesh(roadGeo, roadMat);
    road.position.set(0, -0.075, z);
    road.receiveShadow = true;
    group.add(road);

    // Dashed white centre line
    const dashCount = Math.ceil(GRID_COLS / 2.2);
    const dashW = 0.08, dashH = 0.005, dashD = 0.38;
    const dashMat = new THREE.MeshBasicMaterial({ color: COLORS.roadLine });
    const dashSpacing = GRID_COLS / dashCount;
    for (let i = 0; i < dashCount; i++) {
      const dashGeo  = new THREE.BoxGeometry(dashW, dashH, dashD);
      const dashMesh = new THREE.Mesh(dashGeo, dashMat);
      const xPos = -GRID_COLS / 2 + (i + 0.5) * dashSpacing;
      dashMesh.position.set(xPos, 0.001, z);
      group.add(dashMesh);
    }

    // Vehicles
    data.obstacles.forEach(obs => {
      const mesh = obs.type === 'truck' ? makeTruck() : makeCar();
      mesh.position.set(obs.col * TILE_SIZE, 0, z);
      if (obs.speed < 0) mesh.rotation.y = Math.PI;
      obs.mesh = mesh;
      group.add(mesh);
      obstacles.push(obs);
    });
  }

  function buildRiverLane(group, data, z) {
    // Solid water surface — bright cyan-blue, full width
    const waterGeo = new THREE.BoxGeometry(GRID_COLS, 0.12, LANE_WIDTH);
    const waterMat = new THREE.MeshLambertMaterial({ color: COLORS.water });
    const water    = new THREE.Mesh(waterGeo, waterMat);
    water.position.set(0, -0.06, z);
    water.receiveShadow = true;
    group.add(water);

    // Subtle shimmer strips (slightly darker horizontal bands)
    const shimmerMat = new THREE.MeshLambertMaterial({ color: COLORS.waterDark });
    for (let i = 0; i < 3; i++) {
      const shimGeo  = new THREE.BoxGeometry(GRID_COLS, 0.005, 0.06);
      const shim     = new THREE.Mesh(shimGeo, shimmerMat);
      shim.position.set(0, 0.005, z + (i - 1) * 0.25);
      group.add(shim);
    }

    // Logs
    data.obstacles.forEach(obs => {
      const mesh = makeLog(obs.width);
      mesh.position.set(obs.col * TILE_SIZE, 0.07, z);
      obs.mesh = mesh;
      group.add(mesh);
      obstacles.push(obs);
    });
  }

  // ─── 3D Object Factories ─────────────────────────────────
  // Pure voxel style throughout — only BoxGeometry, matching Crossy Road reference.
  // All objects sit with their base at y=0.

  // Tree: brown rectangular trunk + stacked green cubes (no cones)
  function makeTree() {
    const g = new THREE.Group();

    // Trunk — thin brown box
    const trunkMat = new THREE.MeshLambertMaterial({ color: COLORS.treeTrunk });
    const trunkGeo = new THREE.BoxGeometry(0.20, 0.28, 0.20);
    const trunk    = new THREE.Mesh(trunkGeo, trunkMat);
    trunk.position.y = 0.14;
    trunk.castShadow = true;
    g.add(trunk);

    // Foliage — two stacked green cubes, slightly offset for depth
    const topMat  = new THREE.MeshLambertMaterial({ color: COLORS.treeCube });
    const topMat2 = new THREE.MeshLambertMaterial({ color: COLORS.treeCubeDark });

    // Bottom foliage block (wider)
    const bot    = new THREE.Mesh(new THREE.BoxGeometry(0.56, 0.42, 0.56), topMat);
    bot.position.y = 0.49;
    bot.castShadow = true;
    g.add(bot);

    // Top foliage block (narrower)
    const top    = new THREE.Mesh(new THREE.BoxGeometry(0.40, 0.36, 0.40), topMat2);
    top.position.y = 0.88;
    top.castShadow = true;
    g.add(top);

    return g;
  }

  // Bush: a single squat green cube
  function makeBush() {
    const g   = new THREE.Group();
    const mat = new THREE.MeshLambertMaterial({ color: COLORS.bush });
    const geo = new THREE.BoxGeometry(0.46, 0.32, 0.46);
    const m   = new THREE.Mesh(geo, mat);
    m.position.y = 0.16;
    m.castShadow = true;
    g.add(m);
    return g;
  }

  // Log: a flat brown rectangular plank (BoxGeometry, NOT a cylinder).
  // In the reference, logs are clearly wide flat planks, not round logs.
  function makeLog(length) {
    const g = new THREE.Group();

    // Main plank — flat box, travels along X axis
    const mainGeo = new THREE.BoxGeometry(length, 0.22, 0.72);
    const mainMat = new THREE.MeshLambertMaterial({ color: COLORS.log });
    const main    = new THREE.Mesh(mainGeo, mainMat);
    main.castShadow = true;
    g.add(main);

    // Top face slightly lighter
    const topGeo = new THREE.BoxGeometry(length, 0.02, 0.72);
    const topMat = new THREE.MeshLambertMaterial({ color: COLORS.logTop });
    const top    = new THREE.Mesh(topGeo, topMat);
    top.position.y = 0.12;
    g.add(top);

    // End caps darker
    const capMat = new THREE.MeshLambertMaterial({ color: COLORS.logSide });
    [-1, 1].forEach(side => {
      const capGeo = new THREE.BoxGeometry(0.04, 0.22, 0.72);
      const cap    = new THREE.Mesh(capGeo, capMat);
      cap.position.x = side * (length / 2 + 0.02);
      g.add(cap);
    });

    return g;
  }

  // Car: coloured lower body + white/light upper cabin, pure voxel boxes.
  // Wheels are flat dark boxes protruding slightly from the sides.
  // Bottom sits at y=0 on the road.
  function makeCar() {
    const g         = new THREE.Group();
    const bodyColor = COLORS.carColors[Math.floor(Math.random() * COLORS.carColors.length)];
    const bodyMat   = new THREE.MeshLambertMaterial({ color: bodyColor });
    const cabinMat  = new THREE.MeshLambertMaterial({ color: COLORS.carCabin });
    const darkMat   = new THREE.MeshLambertMaterial({ color: 0x222233 });
    const wheelMat  = new THREE.MeshLambertMaterial({ color: 0x1a1a2a });
    const lightMat  = new THREE.MeshBasicMaterial({ color: 0xffffcc });

    // Lower body — sits on ground, y=0 to y=0.30
    const lowerGeo = new THREE.BoxGeometry(1.10, 0.30, 0.72);
    const lower    = new THREE.Mesh(lowerGeo, bodyMat);
    lower.position.y = 0.15;
    lower.castShadow = true;
    g.add(lower);

    // Upper cabin — white, centred, narrower
    const cabinGeo = new THREE.BoxGeometry(0.66, 0.28, 0.66);
    const cabin    = new THREE.Mesh(cabinGeo, cabinMat);
    cabin.position.y = 0.44;
    cabin.castShadow = true;
    g.add(cabin);

    // Window slots — dark face on front (+X) and rear (-X) of cabin
    const winGeo = new THREE.BoxGeometry(0.03, 0.18, 0.56);
    [0.34, -0.34].forEach(x => {
      const win = new THREE.Mesh(winGeo, darkMat);
      win.position.set(x, 0.44, 0);
      g.add(win);
    });

    // Side window strips
    const sideWinGeo = new THREE.BoxGeometry(0.58, 0.14, 0.03);
    [-0.35, 0.35].forEach(z => {
      const sw = new THREE.Mesh(sideWinGeo, darkMat);
      sw.position.set(0, 0.44, z);
      g.add(sw);
    });

    // Wheels — 4 flat dark boxes, one at each corner, protruding beyond body Z
    // Each wheel: width along X (thin), height=0.18, depth along Z (slightly wider than body)
    const wGeo = new THREE.BoxGeometry(0.20, 0.18, 0.10);
    [
      [ 0.36,  0.09,  0.42],
      [ 0.36,  0.09, -0.42],
      [-0.36,  0.09,  0.42],
      [-0.36,  0.09, -0.42],
    ].forEach(([x, y, z]) => {
      const w = new THREE.Mesh(wGeo, wheelMat);
      w.position.set(x, y, z);
      g.add(w);
    });

    // Headlights — small bright squares on front face (+X)
    const litGeo = new THREE.BoxGeometry(0.04, 0.10, 0.12);
    [-0.20, 0.20].forEach(z => {
      const lit = new THREE.Mesh(litGeo, lightMat);
      lit.position.set(0.56, 0.18, z);
      g.add(lit);
    });

    return g;
  }

  // Truck: bright coloured cab + white cargo box, with visible wheels.
  function makeTruck() {
    const g        = new THREE.Group();
    const cabColor = COLORS.truckCabColors[Math.floor(Math.random() * COLORS.truckCabColors.length)];
    const cabMat   = new THREE.MeshLambertMaterial({ color: cabColor });
    const cargoMat = new THREE.MeshLambertMaterial({ color: COLORS.truckCargo });
    const darkMat  = new THREE.MeshLambertMaterial({ color: 0x222233 });
    const wheelMat = new THREE.MeshLambertMaterial({ color: 0x1a1a2a });
    const lightMat = new THREE.MeshBasicMaterial({ color: 0xffffcc });

    // ── Cab (front, +X side) ──
    const cabLowGeo = new THREE.BoxGeometry(0.72, 0.30, 0.72);
    const cabLow    = new THREE.Mesh(cabLowGeo, cabMat);
    cabLow.position.set(0.80, 0.15, 0);
    cabLow.castShadow = true;
    g.add(cabLow);

    const cabTopGeo = new THREE.BoxGeometry(0.64, 0.30, 0.66);
    const cabTop    = new THREE.Mesh(cabTopGeo, cabMat);
    cabTop.position.set(0.80, 0.45, 0);
    cabTop.castShadow = true;
    g.add(cabTop);

    // Cab windshield
    const windGeo = new THREE.BoxGeometry(0.04, 0.20, 0.58);
    const wind    = new THREE.Mesh(windGeo, darkMat);
    wind.position.set(1.13, 0.46, 0);
    g.add(wind);

    // Cab headlights
    const litGeo = new THREE.BoxGeometry(0.04, 0.10, 0.12);
    [-0.20, 0.20].forEach(z => {
      const lit = new THREE.Mesh(litGeo, lightMat);
      lit.position.set(1.17, 0.16, z);
      g.add(lit);
    });

    // ── Cargo box (rear, -X side) ──
    const cargoGeo = new THREE.BoxGeometry(1.44, 0.54, 0.74);
    const cargo    = new THREE.Mesh(cargoGeo, cargoMat);
    cargo.position.set(-0.44, 0.27, 0);
    cargo.castShadow = true;
    g.add(cargo);

    // Cargo top shade stripe
    const shadeGeo = new THREE.BoxGeometry(1.44, 0.06, 0.75);
    const shadeMat = new THREE.MeshLambertMaterial({ color: 0xccccdd });
    const shade    = new THREE.Mesh(shadeGeo, shadeMat);
    shade.position.set(-0.44, 0.51, 0);
    g.add(shade);

    // Wheels — 6 total: 2 under cab, 4 under cargo
    const wGeo = new THREE.BoxGeometry(0.22, 0.18, 0.10);
    [
      // Cab axle
      [ 0.80, 0.09,  0.42],
      [ 0.80, 0.09, -0.42],
      // Cargo front axle
      [-0.10, 0.09,  0.42],
      [-0.10, 0.09, -0.42],
      // Cargo rear axle
      [-0.80, 0.09,  0.42],
      [-0.80, 0.09, -0.42],
    ].forEach(([x, y, z]) => {
      const w = new THREE.Mesh(wGeo, wheelMat);
      w.position.set(x, y, z);
      g.add(w);
    });

    return g;
  }

  // ─── Chicken (Player) ────────────────────────────────────
  // The chicken's default facing is +Z (toward camera = "up" on screen).
  // All parts are built relative to that facing so rotations in tryHop are correct.
  function buildPlayer() {
    player = new THREE.Group();
    player.name = 'player';

    // Body — centred, sits above ground
    const bodyGeo = new THREE.BoxGeometry(0.38, 0.40, 0.42);
    const bodyMat = new THREE.MeshLambertMaterial({ color: COLORS.chickenBody });
    const body    = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 0.40;
    body.castShadow = true;
    player.add(body);

    // Head — offset forward (+Z) from body centre
    const headGeo = new THREE.BoxGeometry(0.30, 0.28, 0.30);
    const headMat = new THREE.MeshLambertMaterial({ color: COLORS.chickenBody });
    const head    = new THREE.Mesh(headGeo, headMat);
    head.position.set(0, 0.76, 0.10);
    head.castShadow = true;
    player.add(head);
    player.userData.head = head;
    player.userData.headBaseY = 0.76;

    // Comb — on top of head
    const combGeo = new THREE.BoxGeometry(0.08, 0.13, 0.10);
    const combMat = new THREE.MeshLambertMaterial({ color: COLORS.chickenComb });
    const comb    = new THREE.Mesh(combGeo, combMat);
    comb.position.set(0, 0.96, 0.08);
    player.add(comb);

    // Beak — protruding forward (+Z)
    const beakGeo = new THREE.BoxGeometry(0.10, 0.07, 0.14);
    const beakMat = new THREE.MeshLambertMaterial({ color: COLORS.chickenBeak });
    const beak    = new THREE.Mesh(beakGeo, beakMat);
    beak.position.set(0, 0.73, 0.26);
    player.add(beak);

    // Eyes — on the forward face of head, spread left/right
    const eyeGeo = new THREE.SphereGeometry(0.043, 6, 6);
    const eyeMat = new THREE.MeshBasicMaterial({ color: COLORS.chickenEye });
    [-0.10, 0.10].forEach(x => {
      const eye = new THREE.Mesh(eyeGeo, eyeMat);
      eye.position.set(x, 0.78, 0.26);
      player.add(eye);
    });

    // Wings — on the sides (±X)
    const wingGeo = new THREE.BoxGeometry(0.08, 0.24, 0.30);
    const wingMat = new THREE.MeshLambertMaterial({ color: COLORS.chickenWing });
    [-1, 1].forEach(side => {
      const wing = new THREE.Mesh(wingGeo, wingMat);
      wing.position.set(side * 0.25, 0.40, 0);
      wing.castShadow = true;
      player.add(wing);
    });

    // Feet — left and right
    const feetGeo = new THREE.BoxGeometry(0.10, 0.06, 0.18);
    const feetMat = new THREE.MeshLambertMaterial({ color: COLORS.chickenFeet });
    [-1, 1].forEach((side, i) => {
      const foot = new THREE.Mesh(feetGeo, feetMat);
      foot.position.set(side * 0.10, 0.04, 0);
      foot.castShadow = true;
      player.add(foot);
      player.userData['foot' + i] = foot;
    });

    // Drop shadow
    const shadowGeo = new THREE.CircleGeometry(0.28, 12);
    const shadowMat = new THREE.MeshBasicMaterial({
      color: COLORS.shadow,
      transparent: true,
      opacity: 0.28,
    });
    const shadow = new THREE.Mesh(shadowGeo, shadowMat);
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.005;
    player.add(shadow);
    player.userData.shadow = shadow;

    scene.add(player);
    placePlayerAt(0, 0);
  }

  function placePlayerAt(row, col) {
    playerState.row   = row;
    playerState.col   = col;
    playerState.worldX = col * TILE_SIZE;
    playerState.worldZ = -row * LANE_WIDTH;
    player.position.set(playerState.worldX, 0, playerState.worldZ);
    player.rotation.y = 0;
  }

  // ─── Input ───────────────────────────────────────────────
  function onKeyDown(e) {
    if (keysDown[e.code]) return; // already held
    keysDown[e.code] = true;

    // Pause toggle — works during playing or paused
    if (e.code === 'KeyP') {
      if (gameState === 'playing') {
        gameState = 'paused';
        document.getElementById('pause-screen').style.display = 'flex';
        return;
      } else if (gameState === 'paused') {
        gameState = 'playing';
        document.getElementById('pause-screen').style.display = 'none';
        clock.getDelta(); // flush accumulated dt
        return;
      }
    }

    if (gameState !== 'playing') return;

    const dirMap = {
      ArrowUp:    { dr: 1,  dc: 0 },
      ArrowDown:  { dr: -1, dc: 0 },
      ArrowLeft:  { dr: 0,  dc: -1 },
      ArrowRight: { dr: 0,  dc: 1 },
    };

    const dir = dirMap[e.code];
    if (dir) {
      e.preventDefault();
      if (inputQueue.length < 2) inputQueue.push(dir);
    }
  }

  function onKeyUp(e) {
    keysDown[e.code] = false;
  }

  // ─── Game Flow ───────────────────────────────────────────
  function startGame() {
    startScreen.style.display = 'none';
    controlsHint.style.display = 'block';
    gameState = 'playing';
    playerState.invincible = 1.0;
    clock.start();
  }

  function restartGame() {
    // Clear obstacles list
    obstacles = [];
    inputQueue = [];
    keysDown   = {};

    // Remove all lane objects from scene
    laneObjects.forEach(g => { if (g) scene.remove(g); });
    lanes       = [];
    laneObjects = [];

    // Remove and rebuild player
    scene.remove(player);
    buildPlayer();

    score  = 0;
    maxRow = 0;
    scoreDisplay.textContent = '0';

    gameoverScreen.style.display = 'none';
    const wastedEl = document.getElementById('wasted-screen');
    if (wastedEl) wastedEl.style.display = 'none';
    controlsHint.style.display   = 'block';

    buildInitialWorld();

    playerState.dead       = false;
    playerState.hopping    = false;
    playerState.deathAnim  = 0;
    playerState.onLog      = null;
    playerState.logOffsetX = 0;
    playerState.invincible = 1.0;
    gameState = 'playing';
    clock.getDelta(); // reset delta spike
  }

  function triggerDeath(cause) {
    if (playerState.dead || playerState.invincible > 0) return;
    playerState.dead = true;
    playerState.deathAnim = 0;
    playerState.hopping = false;
    inputQueue = [];
    gameState  = 'dead';

    // Update best
    if (score > bestScore) bestScore = score;

    // Show WASTED after a short delay so the spin animation plays first
    setTimeout(() => {
      const wastedEl = document.getElementById('wasted-screen');
      if (wastedEl) {
        // Reset animation so it plays fresh each death
        wastedEl.style.animation = 'none';
        wastedEl.offsetHeight;   // force reflow
        wastedEl.style.animation = '';
        wastedEl.style.display   = 'flex';
      }
    }, 300);
  }

  function showGameOver() {
    // Hide wasted, show full game-over screen
    const wastedEl = document.getElementById('wasted-screen');
    if (wastedEl) wastedEl.style.display = 'none';
    finalScoreEl.textContent = 'Score: ' + score;
    bestScoreEl.textContent  = 'Best: ' + bestScore;
    gameoverScreen.style.display = 'flex';
    controlsHint.style.display   = 'none';
    gameState = 'gameover';
  }

  // ─── Player Update ───────────────────────────────────────
  function updatePlayer(dt) {
    if (playerState.invincible > 0) playerState.invincible -= dt;

    // Death animation — chicken spins and shrinks
    if (playerState.dead) {
      playerState.deathAnim += dt;
      const t = playerState.deathAnim;
      player.rotation.y  += dt * 8;
      player.position.y   = Math.max(0, 0.5 * Math.sin(t * 4) * (1 - t / 0.8));
      player.scale.setScalar(Math.max(0, 1 - t / 0.7));
      if (t > 0.9) showGameOver();
      return;
    }

    if (gameState !== 'playing') return;

    // Process hop queue
    if (!playerState.hopping && inputQueue.length > 0) {
      const dir = inputQueue.shift();
      tryHop(dir.dr, dir.dc);
    }

    // Animate hop
    if (playerState.hopping) {
      playerState.hopT += dt / HOP_DURATION;
      if (playerState.hopT >= 1) {
        playerState.hopT = 1;
        finishHop();
      }

      const t   = playerState.hopT;
      const arc = Math.sin(t * Math.PI) * HOP_HEIGHT;

      playerState.worldX = lerp(playerState.hopFrom.x, playerState.hopTo.x, t);
      playerState.worldZ = lerp(playerState.hopFrom.z, playerState.hopTo.z, t);

      player.position.set(playerState.worldX, arc, playerState.worldZ);

      // Body bob
      if (player.userData.head) {
        player.userData.head.position.y = player.userData.headBaseY + arc * 0.15;
      }
    } else {
      // Riding a log — move player by the same delta the log moved this frame.
      // We store the offset from the log centre at landing, so the player keeps
      // their position on the log rather than snapping to its centre.
      if (playerState.onLog) {
        const logObs = playerState.onLog;
        if (logObs.mesh) {
          playerState.worldX  = logObs.mesh.position.x + playerState.logOffsetX;
          player.position.x   = playerState.worldX;
          playerState.col     = playerState.worldX / TILE_SIZE; // keep as float while riding
        }
      }
      player.position.y = 0;
    }

    // Screen-edge death: kill player when they walk off the visible screen.
    // Compute the visible half-width at ground level from the camera frustum.
    const camZ   = camera.position.z;
    const groundZ = playerState.worldZ;
    const distToGround = Math.abs(camera.position.y); // approximate
    const fovRad = THREE.MathUtils.degToRad(camera.fov);
    const visibleHalfH = distToGround * Math.tan(fovRad / 2);
    const visibleHalfW = visibleHalfH * camera.aspect;
    const screenLeft  = camera.position.x - visibleHalfW - 0.5;
    const screenRight = camera.position.x + visibleHalfW + 0.5;
    if (playerState.worldX < screenLeft || playerState.worldX > screenRight) {
      triggerDeath('bounds');
    }

    // Animate feet while hopping
    if (playerState.hopping) {
      const legSwing = Math.sin(playerState.hopT * Math.PI * 2) * 0.15;
      if (player.userData.foot0) player.userData.foot0.position.z =  0.1 + legSwing;
      if (player.userData.foot1) player.userData.foot1.position.z = -0.1 - legSwing;
    }

    // Decrease invincibility
    if (playerState.invincible < 0) playerState.invincible = 0;
  }

  function tryHop(dr, dc) {
    // Always work from a snapped integer column to prevent float drift
    // breaking left/right movement after log-riding.
    const currentCol = Math.round(playerState.col);
    const newRow     = playerState.row + dr;
    const newCol     = currentCol + dc;

    // Bounds check X
    if (newCol < -HALF_COLS || newCol > HALF_COLS) return;

    // Check if blocked by tree
    const laneData = lanes[newRow + 1000];
    if (laneData && laneData.blockedCols && laneData.blockedCols.has(newCol)) return;

    // Prevent stepping backward off spawn
    if (newRow < -4) return;

    // Face direction of travel.
    // Chicken default facing = +Z (toward camera = down-screen).
    // Camera looks from +Z toward -Z, so screen-up = world -Z.
    //   Up   (dr=1,  -Z)  → face -Z → rotate π
    //   Down (dr=-1, +Z)  → face +Z → rotate 0
    //   Left (dc=-1, -X)  → face -X → rotate -π/2
    //   Right(dc=1,  +X)  → face +X → rotate +π/2
    if      (dr ===  1) player.rotation.y =  Math.PI;
    else if (dr === -1) player.rotation.y =  0;
    else if (dc === -1) player.rotation.y = -Math.PI / 2;
    else if (dc ===  1) player.rotation.y =  Math.PI / 2;

    playerState.hopFrom = {
      x: playerState.worldX,
      z: playerState.worldZ,
    };
    playerState.hopTo = {
      x: newCol * TILE_SIZE,
      z: -newRow * LANE_WIDTH,
    };
    playerState.hopping    = true;
    playerState.hopT       = 0;
    playerState.hopDir     = { dr, dc };
    playerState.onLog      = null;      // stop log-riding during the hop
    playerState.logOffsetX = 0;

    // Generate more world ahead if needed
    if (newRow + GENERATE_AHEAD > getMaxGeneratedRow()) {
      for (let r = getMaxGeneratedRow() + 1; r <= newRow + GENERATE_AHEAD; r++) {
        generateLane(r);
      }
    }
  }

  function finishHop() {
    const dir = playerState.hopDir;
    playerState.row   += dir.dr;
    playerState.worldX = playerState.hopTo.x;
    playerState.worldZ = playerState.hopTo.z;
    playerState.col    = Math.round(playerState.worldX / TILE_SIZE); // always integer
    player.position.set(playerState.worldX, 0, playerState.worldZ);
    playerState.hopping = false;

    // Score: only increase when moving forward
    if (dir.dr === 1 && playerState.row > maxRow) {
      maxRow = playerState.row;
      score  = maxRow;
      scoreDisplay.textContent = score;
    }

    // Land on river? Check for log
    const lane = lanes[playerState.row + 1000];
    if (lane && lane.type === LANE_TYPES.RIVER) {
      const log = getLogUnderPlayer();
      if (log) {
        playerState.onLog     = log;
        // Record how far the player landed from the log's centre.
        // This offset is preserved as the log moves, so the player rides
        // at their actual landing position rather than snapping to centre.
        playerState.logOffsetX = playerState.worldX - log.mesh.position.x;
      } else {
        triggerDeath('water');
      }
    } else {
      playerState.onLog      = null;
      playerState.logOffsetX = 0;
    }

    // Clean up old lanes far behind
    cullOldLanes();
  }

  function getLogUnderPlayer() {
    const lane = lanes[playerState.row + 1000];
    if (!lane || lane.type !== LANE_TYPES.RIVER) return null;

    for (const obs of lane.obstacles) {
      if (obs.type !== 'log' || !obs.mesh) continue;
      // The lane group is at x=0, so log world X = mesh local X
      const logWorldX = obs.mesh.position.x;
      const halfW = obs.width / 2;
      if (playerState.worldX >= logWorldX - halfW - 0.2 &&
          playerState.worldX <= logWorldX + halfW + 0.2) {
        return obs;
      }
    }
    return null;
  }

  function getMaxGeneratedRow() {
    let max = 0;
    for (let i = 0; i < lanes.length; i++) {
      if (lanes[i]) max = Math.max(max, lanes[i].row);
    }
    return max;
  }

  function cullOldLanes() {
    const minKeep = playerState.row - 8;
    for (let r = minKeep - 10; r < minKeep; r++) {
      const idx = r + 1000;
      if (laneObjects[idx]) {
        scene.remove(laneObjects[idx]);
        laneObjects[idx] = undefined;
      }
      if (lanes[idx]) {
        // Remove obstacle refs
        if (lanes[idx].obstacles) {
          lanes[idx].obstacles.forEach(obs => {
            const i = obstacles.indexOf(obs);
            if (i !== -1) obstacles.splice(i, 1);
          });
        }
        lanes[idx] = undefined;
      }
    }
  }

  // ─── Obstacles Update ────────────────────────────────────
  function updateObstacles(dt) {
    const bound = (HALF_COLS + 4) * TILE_SIZE;

    obstacles.forEach(obs => {
      if (!obs.mesh) return;

      obs.mesh.position.x += obs.speed * dt;

      // Wrap around
      if (obs.speed > 0 && obs.mesh.position.x > bound) {
        obs.mesh.position.x = -bound;
      } else if (obs.speed < 0 && obs.mesh.position.x < -bound) {
        obs.mesh.position.x = bound;
      }

      obs.col = obs.mesh.position.x / TILE_SIZE;
    });

    // Car collision check
    if (!playerState.dead && !playerState.hopping && gameState === 'playing') {
      const lane = lanes[playerState.row + 1000];
      if (lane && lane.type === LANE_TYPES.ROAD) {
        lane.obstacles.forEach(obs => {
          if (!obs.mesh) return;
          const obsWorldX = obs.mesh.position.x; // lane group is at x=0
          const halfW = obs.width / 2 + 0.1;
          if (Math.abs(playerState.worldX - obsWorldX) < halfW) {
            triggerDeath('car');
          }
        });
      }
    }

    // Also check during hop landing frames
    if (!playerState.dead && playerState.hopping) {
      const targetRow = playerState.row + (playerState.hopDir?.dr || 0);
      const lane = lanes[targetRow + 1000];
      if (lane && lane.type === LANE_TYPES.ROAD && playerState.hopT > 0.7) {
        lane.obstacles.forEach(obs => {
          if (!obs.mesh) return;
          const obsWorldX = obs.mesh.position.x; // lane group is at x=0
          const halfW = obs.width / 2 + 0.08;
          const targetX = playerState.hopTo.x;
          if (Math.abs(targetX - obsWorldX) < halfW) {
            triggerDeath('car');
          }
        });
      }
    }

    // River: player not on log while on river row (checked each frame)
    if (!playerState.dead && !playerState.hopping && gameState === 'playing') {
      const lane = lanes[playerState.row + 1000];
      if (lane && lane.type === LANE_TYPES.RIVER) {
        if (playerState.onLog) {
          // Still on log? Player can move along the log but must stay within its span.
          const log = playerState.onLog;
          if (log.mesh) {
            const logWorldX = log.mesh.position.x;
            const halfW = log.width / 2;
            if (playerState.worldX < logWorldX - halfW - 0.15 ||
                playerState.worldX > logWorldX + halfW + 0.15) {
              triggerDeath('water');
            }
          }
        } else {
          triggerDeath('water');
        }
      }
    }
  }

  // ─── Main Loop ───────────────────────────────────────────
  function animate() {
    requestAnimationFrame(animate);

    const dt = Math.min(clock.getDelta(), 0.05); // cap delta to avoid spiral

    if (gameState === 'playing' || gameState === 'dead') {
      updatePlayer(dt);
      updateObstacles(dt);
      updateCamera(dt);
    }
    // When paused, still render but don't update game logic

    renderer.render(scene, camera);
  }

  // ─── Resize ──────────────────────────────────────────────
  function onResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }

  // ─── Helpers ─────────────────────────────────────────────
  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  // ─── Boot ────────────────────────────────────────────────
  init();

})();
