let motionStages = [];
const SERIAL_POLL_INTERVAL_MS = 16;

function buildMotionStages() {
  const settings = settingsFromForm();
  const stages = [];
  const controls = [];
  if (settings.base_variant === "six_keys") {
    [10, 16, 14, 1, 0, 15].forEach((pin, index) => controls.push({ index, label: `Key ${index + 1} · D${pin}` }));
  }
  if (["buttons", "full"].includes(settings.control_variant)) {
    const offset = controls.length;
    const labels = settings.controller_buttons_mode === "kill"
      ? ["Rotation lock · D5", "Movement lock · D7"]
      : ["Top shortcut 1 · D5", "Top shortcut 2 · D7"];
    labels.forEach((label, index) => controls.push({ index: offset + index, label }));
  }
  if (controls.length) {
    stages.push({ autoStart: true, kind: "buttons", mode: "1", controls, title: "Press every key", help: "Press and release each key once. Detected keys turn green automatically.", done: "All keys detected", wait: 0 });
  }
  if (["wheel", "full"].includes(settings.control_variant)) {
    stages.push({ autoStart: true, mode: "9", title: "Turn the wheel both ways", help: "Rotate the wheel clockwise and counter-clockwise, then confirm both directions respond.", done: "Wheel responds both ways", wait: 0 });
  }
  if (["buttons", "full"].includes(settings.control_variant) && settings.controller_buttons_mode === "kill") {
    stages.push({ autoStart: true, mode: "6", title: "Try the precision buttons", help: "Hold Rotation lock for translation only, or Movement lock for rotation only. Double-click either button to toggle one-axis-only precision for its remaining motion group.", done: "Both locks work", wait: 0 });
  }
  stages.push(
    { autoStart: false, mode: "11", title: "Find the centre", help: "Take your hand off the controller. It will measure its resting position and idle noise.", start: "Find centre", done: "Centre found", wait: 2600 },
    { autoStart: false, mode: "20", title: "Capture full travel", help: "Take your time for 30 seconds. Push, pull, twist, and tilt fully in every direction, making sure you reach the complete travel in each direction.", start: "Start 30-second check", done: "Travel captured", wait: 32500 },
    { autoStart: true, mode: "4", title: "Verify all six motions", help: "Check move left/right, forward/back, up/down, and rotation around all three axes.", done: "All motions work", wait: 0 },
  );
  return stages;
}

const state = {
  currentScreen: 0,
  status: null,
  configured: false,
  canTune: false,
  installed: false,
  installing: false,
  completed: false,
  serialSequence: 0,
  serialTimer: null,
  serialPollInFlight: false,
  statusTimer: null,
  installProgressTimer: null,
  motionStage: 0,
  motionStageRunning: false,
  motionStageActivating: false,
  connectedForCalibration: false,
  detectedControls: new Set(),
  tuningBackScreen: 5,
  autoConnecting: false,
  autoConnectAttempted: false,
  telemetry: { translation: [0, 0, 0], rotation: [0, 0, 0], keys: [], wheel: 0 },
  keyMapping: [],
  axisMapping: { inverted: [], swapGroups: false },
  inspectMode: new URLSearchParams(window.location.search).has("inspect"),
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value) => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function toast(message, isError = false) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.toggle("error", isError);
  element.classList.add("visible");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => element.classList.remove("visible"), 4200);
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function showScreen(index, updateHistory = true) {
  const bounded = Math.max(0, Math.min(7, Number(index)));
  const previous = state.currentScreen;
  state.currentScreen = bounded;
  $$(".setup-screen").forEach((screen) => {
    const active = Number(screen.dataset.screen) === bounded;
    screen.classList.toggle("active", active);
    screen.setAttribute("aria-hidden", String(!active));
  });
  $$("[data-rail-step]").forEach((item) => {
    const step = Number(item.dataset.railStep);
    item.classList.toggle("active", step === bounded);
    item.classList.toggle("complete", step < bounded || (step === 7 && state.completed));
  });
  $("#mobileProgressBar").style.width = `${bounded === 0 ? 0 : (bounded / 7) * 100}%`;
  if (updateHistory) window.history.replaceState(null, "", bounded ? `#step-${bounded}` : "#welcome");
  if (bounded === 1 || bounded === 4) refreshStatus(true);
  if (bounded === 5) {
    if (previous !== 5) state.autoConnectAttempted = false;
    prepareMotionConnection();
  }
  if (bounded === 4) updateReview();
  if (bounded === 6) updateTuningAvailability();
  window.scrollTo({ top: 0, behavior: "smooth" });
  const heading = $(`.setup-screen[data-screen="${bounded}"] h1`);
  if (heading) {
    heading.tabIndex = -1;
    window.setTimeout(() => heading.focus({ preventScroll: true }), 120);
  }
}

function settingsFromForm() {
  const edition = document.querySelector('input[name="edition"]:checked').value;
  return {
    edition,
    controller_style: $("#controllerStyle").value,
    handedness: edition === "free" ? "symmetric" : $("#handedness").value,
    base_variant: edition === "free" ? "simple" : $("#baseVariant").value,
    control_variant: edition === "free" ? "simple" : $("#controlVariant").value,
    controller_buttons_mode: $("#buttonMode").value,
    wheel_axis: Number($("#wheelAxis").value),
    led_ring_enabled: false,
    led_count: 24,
    progmode_enabled: true,
    exclusive_mode: $("#exclusiveMode").checked,
    priority_z: $("#exclusiveMode").checked,
  };
}

function applySettings(settings) {
  const edition = document.querySelector(`input[name="edition"][value="${settings.edition}"]`);
  const shape = document.querySelector(`input[name="controllerStyleChoice"][value="${settings.controller_style}"]`);
  if (edition) edition.checked = true;
  if (shape) shape.checked = true;
  $("#controllerStyle").value = settings.controller_style;
  $("#handedness").value = settings.handedness;
  $("#baseVariant").value = settings.base_variant;
  $("#controlVariant").value = settings.control_variant;
  $("#buttonMode").value = settings.controller_buttons_mode;
  $("#wheelAxis").value = String(settings.wheel_axis);
  $("#exclusiveMode").checked = settings.exclusive_mode;
  updateVariantUI(false);
}

function checkTemplate(label, ok, detail) {
  return `<div class="${ok ? "ok" : "warn"}"><b>${ok ? "✓" : "!"} ${escapeHtml(label)}</b><small>${escapeHtml(detail)}</small></div>`;
}

function renderStatus(data) {
  state.status = data;
  const portable = data.mode === "portable";
  const installReady = portable ? data.installer.ready : data.platformio.ok;
  const ports = data.device.ports || [];

  $("#checks").innerHTML = [
    checkTemplate("Setup app", true, portable ? "Portable edition" : `Python ${data.python.version}`),
    checkTemplate(portable ? "Verified firmware" : "Build tools", installReady, portable ? `${data.installer.variantCount} variants ready` : (data.platformio.version || "PlatformIO missing")),
    checkTemplate("Configuration", data.config.ok, data.config.ok ? "Saved locally" : "Created before installation"),
    checkTemplate("Controller", data.device.ok, data.device.ok ? ports.join(", ") : "Not connected"),
  ].join("");

  state.configured = data.config.ok;
  state.canTune = data.config.ok && data.device.ok;
  populatePorts(ports);
  renderConnection(data.device.ok, ports[0]);
  configureInstallMode(portable);
  updateActionAvailability();
}

function renderConnection(connected, port) {
  $("#connectStage").classList.toggle("detected", connected);
  $("#detectingState").hidden = connected;
  $("#detectedState").hidden = !connected;
  $("#connectContinue").disabled = !connected;
  $("#detectedPort").textContent = connected ? `${friendlyPort(port)} · Ready` : "USB device connected";
  if (!state.connectedForCalibration) $("#connectCalibration").disabled = !connected;
}

function friendlyPort(port = "") {
  if (/^COM\d+$/i.test(port)) return `USB controller on ${port}`;
  if (port.includes("usbmodem")) return "USB controller detected";
  return port.split("/").pop() || "USB controller detected";
}

function populatePorts(ports) {
  const select = $("#devicePort");
  const selected = select.value;
  select.innerHTML = ports.length
    ? ports.map((port) => `<option value="${escapeHtml(port)}">${escapeHtml(friendlyPort(port))}</option>`).join("")
    : '<option value="">No device detected</option>';
  if (ports.includes(selected)) select.value = selected;
}

function configureInstallMode(portable) {
  $("#installHelp").textContent = portable
    ? "We found the right verified firmware. Keep the controller connected and still."
    : "We’ll build the matching firmware, then install it on the connected controller.";
  $("#installFirmware").firstChild.textContent = portable ? "Install firmware " : "Build and install ";
}

function updateActionAvailability() {
  const hasDevice = Boolean(state.status && state.status.device.ok);
  state.canTune = hasDevice && state.configured;
  $("#installFirmware").disabled = state.installing || !hasDevice || !state.configured;
  $("#connectCalibration").disabled = !hasDevice || state.connectedForCalibration;
  $("#resumeTuning").hidden = !state.canTune;
}

async function refreshStatus(silent = false) {
  if (!silent) $("#refreshStatus").disabled = true;
  try {
    renderStatus(await request("/api/status"));
  } catch (error) {
    if (!silent) toast(error.message, true);
  } finally {
    if (!silent) $("#refreshStatus").disabled = false;
  }
}

function updateVariantUI(markDirty = true) {
  const shape = document.querySelector('input[name="controllerStyleChoice"]:checked');
  if (shape) $("#controllerStyle").value = shape.value;
  const edition = document.querySelector('input[name="edition"]:checked').value;
  updateDependentModelOptions(edition === "free");
  const settings = settingsFromForm();
  const isFree = settings.edition === "free";
  const hasWheel = ["wheel", "full"].includes(settings.control_variant);
  const hasButtons = ["buttons", "full"].includes(settings.control_variant);
  $("#completeOptions").hidden = isFree;
  $$(".wheel-option").forEach((element) => { element.hidden = !hasWheel; });
  $$(".button-option").forEach((element) => { element.hidden = !hasButtons; });
  $("#precisionButtonGuide").hidden = !hasButtons || settings.controller_buttons_mode !== "kill";
  $("#buttonModeHelp").textContent = settings.controller_buttons_mode === "kill"
    ? "Steady difficult 6DOF moves by temporarily removing either rotation or movement."
    : "Use the two controller buttons as additional shortcuts sent directly to your CAD application.";
  $("#modelContinue").disabled = false;
  updateReview();
  setupMotionStages();
  renderKeyMapping();
  if (markDirty) {
    state.configured = false;
    state.installed = false;
    state.completed = false;
    resetInstallUI();
    updateActionAvailability();
  }
}

function hidKeyCount(settings = settingsFromForm()) {
  const base = settings.base_variant === "six_keys" ? 6 : 0;
  const top = ["buttons", "full"].includes(settings.control_variant) && settings.controller_buttons_mode === "hid" ? 2 : 0;
  return base + top;
}

function renderLiveController() {
  const settings = settingsFromForm();
  const hasBaseKeys = settings.base_variant === "six_keys";
  const hasSideKeys = ["buttons", "full"].includes(settings.control_variant);
  const key = (index) => `<i data-live-key="${index}">${index + 1}</i>`;
  $("#liveTopKeys").innerHTML = hasBaseKeys ? [0, 1, 2].map(key).join("") : "";
  $("#liveBottomKeys").innerHTML = hasBaseKeys ? [3, 4, 5].map(key).join("") : "";
  const sideOffset = hasBaseKeys ? 6 : 0;
  $("#liveSideKeys").innerHTML = hasSideKeys ? [sideOffset, sideOffset + 1].map(key).join("") : "";
  $(".controller-silhouette").classList.toggle("no-wheel", !["wheel", "full"].includes(settings.control_variant));
}

function updateLiveVisualization(telemetry) {
  if (!telemetry) return;
  state.telemetry = telemetry;
  const translation = telemetry.translation || [0, 0, 0];
  const rotation = telemetry.rotation || [0, 0, 0];
  const clamp = (value, limit) => Math.max(-limit, Math.min(limit, Number(value) || 0));
  const tx = clamp(translation[0] / 350, 1);
  const ty = clamp(translation[1] / 350, 1);
  const tz = clamp(translation[2] / 350, 1);
  const rx = clamp(rotation[0] / 350, 1);
  const ry = clamp(rotation[1] / 350, 1);
  const rz = clamp(rotation[2] / 350, 1);
  // The telemetry follows HID axis names. In the perspective view, HID TY is depth and HID TZ is
  // vertical. The cube rotations use the matching drawn axes, with signs chosen for physical motion.
  $("#motionCubePosition").style.transform = `translate3d(${tx * 27}px, ${tz * 25}px, ${ty * 30}px) scale(${1 + ty * 0.08})`;
  $("#motionCube").style.transform = `rotateX(${-18 - rx * 38}deg) rotateY(${28 - rz * 42}deg) rotateZ(${-ry * 40}deg)`;
  const knobScale = 1 - tz * 0.18;
  $("#liveKnob").style.transform = `translate(${tx * 8}px, ${ty * 8}px) scale(${knobScale}) rotateX(${-rx * 8}deg) rotateY(${-ry * 8}deg) rotateZ(${rz * 8}deg)`;
  const pressed = new Set(telemetry.keys || []);
  $$('[data-live-key]').forEach((key) => key.classList.toggle("pressed", pressed.has(Number(key.dataset.liveKey))));
  const wheelDirection = Number(telemetry.wheelDirection) || 0;
  $("#liveWheelUp").classList.toggle("active", wheelDirection > 0);
  $("#liveWheelDown").classList.toggle("active", wheelDirection < 0);
  const values = [...translation, ...rotation].map((value) => Math.abs(Number(value) || 0));
  const maxValue = Math.max(...values);
  const activeKeys = pressed.size;
  $("#motionSummary").textContent = activeKeys
    ? `${activeKeys} key${activeKeys === 1 ? "" : "s"} pressed`
    : maxValue > 8 ? "Live 6DOF motion detected" : "Controller resting at centre";
}

function updateDependentModelOptions(isFree) {
  const select = $("#baseVariant");
  const previous = select.value;
  const symmetric = isFree || $("#handedness").value === "symmetric";
  const options = symmetric
    ? [["simple", "No Base Keys"]]
    : [["simple", "No Base Keys"], ["six_keys", "6 Base Keys"]];
  select.innerHTML = options.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
  select.value = options.some(([value]) => value === previous) ? previous : "simple";
}

function updateReview() {
  const settings = settingsFromForm();
  const edition = settings.edition === "free" ? "Free / Simple" : "Complete / Custom";
  const shape = settings.controller_style === "knob" ? "Knob" : "Joystick";
  const build = settings.edition === "free" ? "" : ` · ${settings.base_variant === "six_keys" ? "6 Base Keys" : "No Base Keys"}`;
  $("#reviewModel").textContent = `${edition} · ${shape}${build}`;
  const features = [];
  if (["wheel", "full"].includes(settings.control_variant)) features.push("Wheel");
  if (["buttons", "full"].includes(settings.control_variant)) features.push("Top buttons");
  if (settings.exclusive_mode) features.push("Intentional motion");
  $("#reviewFeatures").textContent = features.length ? features.join(" · ") : "Simple controls";
}

async function saveConfiguration() {
  const result = await request("/api/configure", {
    method: "POST",
    body: JSON.stringify(settingsFromForm()),
  });
  $("#configPreview").textContent = result.preview;
  state.configured = true;
  if (state.status && result.installer) state.status.installer = result.installer;
  updateActionAvailability();
  return result;
}

async function prepareFirmware() {
  const button = $("#prepareFirmware");
  button.disabled = true;
  button.innerHTML = 'Preparing… <span class="spinner"></span>';
  try {
    await saveConfiguration();
    await refreshStatus(true);
    showScreen(4);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.innerHTML = "Continue <span>→</span>";
  }
}

function showInstallState(name) {
  $$(".install-state").forEach((element) => {
    element.hidden = element.id !== name;
    element.classList.toggle("active", element.id === name);
  });
}

function startInstallProgress() {
  let value = 10;
  $("#installProgressBar").style.width = `${value}%`;
  window.clearInterval(state.installProgressTimer);
  state.installProgressTimer = window.setInterval(() => {
    value = Math.min(88, value + Math.max(2, Math.round((90 - value) / 7)));
    $("#installProgressBar").style.width = `${value}%`;
  }, 420);
}

function resetInstallUI() {
  window.clearInterval(state.installProgressTimer);
  state.installing = false;
  showInstallState("installIdle");
  $("#installContinue").hidden = true;
  $("#installFirmware").hidden = false;
  $("#installFirmware").innerHTML = "Install firmware <span>→</span>";
}

async function installFirmware() {
  if (state.installing) return;
  if (!state.status || !state.status.device.ok) {
    toast("Connect the ErgonoMouse before installing.", true);
    showScreen(1);
    return;
  }
  const portable = state.status.mode === "portable";
  const button = $("#installFirmware");
  state.installing = true;
  button.disabled = true;
  showInstallState("installWorking");
  startInstallProgress();
  try {
    let result;
    if (portable) {
      result = await request("/api/install", {
        method: "POST",
        body: JSON.stringify({ port: $("#devicePort").value || null }),
      });
      if (!result.ok) throw new Error(result.message);
    } else {
      $("#installWorkingText").textContent = "Building the matching firmware. Don’t unplug the controller.";
      const build = await request("/api/build", { method: "POST", body: "{}" });
      $("#terminalOutput").textContent = build.output || "";
      if (!build.ok) throw new Error("Firmware could not be built. Open technical details for the log.");
      $("#installWorkingText").textContent = "Installing firmware. Don’t unplug the controller.";
      result = await request("/api/flash", { method: "POST", body: "{}" });
      $("#terminalOutput").textContent += `\n${result.output || ""}`;
      if (!result.ok) throw new Error("Firmware could not be installed. Open technical details for the log.");
    }
    window.clearInterval(state.installProgressTimer);
    $("#installProgressBar").style.width = "100%";
    state.installing = false;
    state.installed = true;
    showInstallState("installSuccess");
    button.hidden = true;
    $("#installContinue").hidden = false;
    toast("Firmware installed successfully.");
    await refreshStatus(true);
  } catch (error) {
    window.clearInterval(state.installProgressTimer);
    state.installing = false;
    state.installed = false;
    $("#installRecovery").textContent = error.message;
    showInstallState("installFailure");
    button.hidden = false;
    button.disabled = false;
    button.innerHTML = "Try again <span>↻</span>";
    toast(error.message, true);
  }
}

function setupMotionStages() {
  motionStages = buildMotionStages();
  state.motionStage = 0;
  state.motionStageRunning = false;
  state.motionStageActivating = false;
  state.detectedControls = new Set();
  const dots = $("#stageDots");
  dots.innerHTML = motionStages.map((_, index) => `<button type="button" aria-label="Check ${index + 1}" data-stage-dot="${index}"></button>`).join("");
  renderMotionStage();
  renderLiveController();
}

function renderMotionStage() {
  const index = Math.min(state.motionStage, motionStages.length - 1);
  const stage = motionStages[index];
  const checklist = $("#controlChecklist");
  const isButtonCheck = state.motionStage < motionStages.length && stage.kind === "buttons";
  checklist.hidden = !isButtonCheck;
  checklist.innerHTML = isButtonCheck
    ? stage.controls.map((control) => `<span class="${state.detectedControls.has(control.index) ? "detected" : ""}" data-control-index="${control.index}">${escapeHtml(control.label)}</span>`).join("")
    : "";
  $("#motionCounter").textContent = state.motionStage >= motionStages.length ? "Checks complete" : `Check ${index + 1} of ${motionStages.length}`;
  $("#motionStageTitle").textContent = state.motionStage >= motionStages.length ? "Everything responds" : stage.title;
  $("#motionStageHelp").textContent = state.motionStage >= motionStages.length ? "The controller is ready to finish setup." : stage.help;
  const detectedAll = !isButtonCheck || stage.controls.every((control) => state.detectedControls.has(control.index));
  $("#runMotionStage").textContent = state.motionStageActivating
    ? "Preparing…"
    : state.motionStageRunning
      ? (isButtonCheck && !detectedAll ? `${state.detectedControls.size} of ${stage.controls.length} detected` : stage.done)
      : (stage.start || "Waiting for connection");
  $("#runMotionStage").disabled = !state.connectedForCalibration || state.motionStage >= motionStages.length || state.motionStageActivating || (state.motionStageRunning && !detectedAll);
  $$('[data-stage-dot]').forEach((dot, dotIndex) => {
    dot.classList.toggle("active", dotIndex === state.motionStage);
    dot.classList.toggle("complete", dotIndex < state.motionStage);
  });
  if (state.motionStage >= motionStages.length) {
    $("#finishCalibration").disabled = false;
    $("#runMotionStage").hidden = true;
  } else {
    $("#runMotionStage").hidden = false;
    if (stage.autoStart && state.connectedForCalibration && !state.motionStageRunning && !state.motionStageActivating) {
      window.setTimeout(activateAutomaticMotionStage, 0);
    }
  }
}

async function startCurrentMotionStage() {
  if (state.motionStage >= motionStages.length || state.motionStageRunning || state.motionStageActivating) return;
  const stage = motionStages[state.motionStage];
  const button = $("#runMotionStage");
  state.motionStageActivating = true;
  renderMotionStage();
  try {
    await request("/api/serial/command", { method: "POST", body: JSON.stringify({ mode: stage.mode }) });
    if (stage.kind === "buttons") state.detectedControls = new Set();
    state.motionStageRunning = true;
    state.motionStageActivating = false;
    renderMotionStage();
    if (stage.wait) {
      button.disabled = true;
      button.textContent = "Measuring…";
      window.setTimeout(() => {
        button.disabled = false;
        button.textContent = stage.done;
      }, stage.wait);
    }
    $("#calibrationTerminal").hidden = false;
  } catch (error) {
    state.motionStageActivating = false;
    renderMotionStage();
    toast(error.message, true);
  }
}

function activateAutomaticMotionStage() {
  const stage = motionStages[state.motionStage];
  if (stage?.autoStart) startCurrentMotionStage();
}

async function connectCalibration(showErrors = true) {
  state.autoConnectAttempted = true;
  $("#connectCalibration").disabled = true;
  try {
    const result = await request("/api/serial/open", {
      method: "POST",
      body: JSON.stringify({ port: $("#devicePort").value }),
    });
    if (!result.ok) throw new Error(result.error || "Could not connect");
    state.connectedForCalibration = true;
    $("#calibrationConnectCard").classList.add("connected");
    $("#calibrationConnectTitle").textContent = "Live connection ready";
    $("#calibrationConnectHelp").textContent = friendlyPort(result.port || $("#devicePort").value);
    $("#connectCalibration").hidden = true;
    $("#disconnectCalibration").hidden = false;
    $("#disconnectCalibration").disabled = false;
    $("#calibrationTerminal").hidden = false;
    $("#calibrationOutput").textContent = "Connected. Live checks begin automatically.\n";
    $("#calibrationOutputPreview").textContent = "Connected. Live checks begin automatically.";
    setLiveDataExpanded(false);
    state.serialSequence = 0;
    window.clearInterval(state.serialTimer);
    state.serialTimer = window.setInterval(pollSerialOutput, SERIAL_POLL_INTERVAL_MS);
    await request("/api/serial/command", { method: "POST", body: JSON.stringify({ mode: "40" }) });
    renderMotionStage();
    return true;
  } catch (error) {
    if (showErrors) toast(error.message, true);
    updateActionAvailability();
    return false;
  }
}

async function prepareMotionConnection() {
  if (state.inspectMode || state.connectedForCalibration || state.autoConnecting || state.autoConnectAttempted) return;
  state.autoConnecting = true;
  try {
    await refreshStatus(true);
    if (!state.status?.device?.ok) return;
    $("#calibrationConnectTitle").textContent = "Connecting automatically…";
    $("#calibrationConnectHelp").textContent = "Opening the local live link to your controller.";
    const connected = await connectCalibration(false);
    if (!connected) {
      $("#calibrationConnectTitle").textContent = "Connect for testing";
      $("#calibrationConnectHelp").textContent = "Automatic connection failed. Select Connect to retry.";
    }
  } finally {
    state.autoConnecting = false;
  }
}

async function disconnectCalibration() {
  window.clearInterval(state.serialTimer);
  state.serialTimer = null;
  try {
    await request("/api/serial/close", { method: "POST", body: "{}" });
  } catch (error) {
    toast(error.message, true);
  }
  state.connectedForCalibration = false;
  $("#calibrationConnectCard").classList.remove("connected");
  $("#calibrationConnectTitle").textContent = "Connect for testing";
  $("#calibrationConnectHelp").textContent = "This opens a private live link to the controller.";
  $("#connectCalibration").hidden = false;
  $("#disconnectCalibration").hidden = true;
  updateActionAvailability();
  updateTuningAvailability();
  renderMotionStage();
}

async function runMotionStage() {
  if (state.motionStage >= motionStages.length) return;
  if (state.motionStageRunning) {
    state.motionStage += 1;
    state.motionStageRunning = false;
    state.motionStageActivating = false;
    request("/api/serial/command", { method: "POST", body: JSON.stringify({ mode: "40" }) }).catch(() => {});
    renderMotionStage();
    return;
  }
  await startCurrentMotionStage();
}

async function pollSerialOutput() {
  if (state.serialPollInFlight) return;
  state.serialPollInFlight = true;
  try {
    const result = await request(`/api/serial/output?after=${state.serialSequence}`);
    state.serialSequence = result.sequence;
    updateLiveVisualization(result.telemetry);
    if (result.lines.length) {
      const output = $("#calibrationOutput");
      const newText = result.lines.map((line) => line.text).join("\n");
      output.textContent += `${newText}\n`;
      $("#calibrationOutputPreview").textContent = result.lines[result.lines.length - 1].text;
      if (output.textContent.length > 30000) output.textContent = output.textContent.slice(-24000);
      output.scrollTop = output.scrollHeight;
      const stage = motionStages[state.motionStage];
      if (state.motionStageRunning && stage?.kind === "buttons") {
        let changed = false;
        result.lines.forEach((line) => {
          for (const match of line.text.matchAll(/K(\d+):0/g)) {
            const index = Number(match[1]);
            if (stage.controls.some((control) => control.index === index) && !state.detectedControls.has(index)) {
              state.detectedControls.add(index);
              changed = true;
            }
          }
        });
        if (changed) renderMotionStage();
      }
    }
    if (!result.connected && state.connectedForCalibration) disconnectCalibration();
  } catch (error) {
    window.clearInterval(state.serialTimer);
  } finally {
    state.serialPollInFlight = false;
  }
}

function setLiveDataExpanded(expanded) {
  $("#calibrationOutput").hidden = !expanded;
  $("#calibrationOutputPreview").hidden = expanded;
  $("#toggleLiveData").textContent = expanded ? "Collapse" : "Expand";
  $("#calibrationTerminal").classList.toggle("expanded", expanded);
}

function continueToTuning() {
  state.tuningBackScreen = 5;
  request("/api/serial/command", { method: "POST", body: JSON.stringify({ mode: "40" }) }).catch(() => {});
  showScreen(6);
  loadKeyMapping();
  loadAxisMapping();
}

async function enterDirectTuning(returnScreen) {
  state.tuningBackScreen = returnScreen;
  await refreshStatus(true);
  if (!state.status?.device?.ok) {
    toast("Connect your ErgonoMouse before fine-tuning.", true);
    return;
  }
  if (!state.connectedForCalibration && !await connectCalibration()) return;
  showScreen(6);
  await Promise.all([loadKeyMapping(), loadAxisMapping()]);
}

async function leaveTuning() {
  const target = state.tuningBackScreen;
  if (target !== 5 && state.connectedForCalibration) await disconnectCalibration();
  showScreen(target);
}

const tuningLabels = ["", "Very gentle", "Gentle", "Softer", "Relaxed", "Balanced", "Responsive", "Quick", "Fast", "Very fast"];
const stabilityLabels = ["", "Very light", "Light", "Low", "Moderate", "Balanced", "Steady", "Firm", "Strong", "Very firm"];

function tuningPayload() {
  return {
    movement: Number($("#translationTune").value),
    vertical: Number($("#verticalTune").value),
    rotation: Number($("#rotationTune").value),
    stability: Number($("#stabilityTune").value),
    curveMode: $("#curveMode").value,
    curvePrecision: Number($("#curvePrecision").value),
    curveBoost: Number($("#curveBoost").value),
  };
}

function renderTuningLabels() {
  [["translationTune", tuningLabels], ["verticalTune", tuningLabels], ["rotationTune", tuningLabels], ["stabilityTune", stabilityLabels], ["curvePrecision", stabilityLabels], ["curveBoost", tuningLabels]].forEach(([id, labels]) => {
    $(`output[for="${id}"]`).textContent = labels[Number($(`#${id}`).value)];
  });
  const curveMode = $("#curveMode").value;
  $("#curveModeLabel").textContent = $("#curveMode").selectedOptions[0].textContent;
  $$(".curve-adjustment").forEach((row) => { row.hidden = curveMode === "linear"; });
  $$(".adaptive-only").forEach((row) => { row.hidden = curveMode !== "adaptive"; });
}

function renderKeyMapping(mapping = state.keyMapping) {
  const count = hidKeyCount();
  $("#keyMappingCard").hidden = count === 0;
  if (!count) return;
  if (!Array.isArray(mapping) || mapping.length !== count) mapping = Array.from({ length: count }, (_, index) => index + 1);
  state.keyMapping = mapping;
  const options = Array.from({ length: count }, (_, index) => `<option value="${index + 1}">Key ${index + 1}</option>`).join("");
  $("#keyMapRows").innerHTML = mapping.map((logical, physical) => `<label class="key-map-row"><span>Physical ${physical + 1}</span><select aria-label="Logical key for physical key ${physical + 1}" data-key-map="${physical}">${options}</select></label>`).join("");
  $$('[data-key-map]').forEach((select, index) => {
    select.value = String(mapping[index]);
    select.disabled = !state.connectedForCalibration;
  });
}

async function loadKeyMapping() {
  const count = hidKeyCount();
  renderKeyMapping();
  if (!count || !state.connectedForCalibration) return;
  try {
    const result = await request("/api/serial/keymap");
    renderKeyMapping(result.mapping);
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveKeyMapping({ quiet = false } = {}) {
  const mapping = $$('[data-key-map]').map((select) => Number(select.value));
  if (new Set(mapping).size !== mapping.length) {
    throw new Error("Assign each logical key exactly once.");
  }
  if (!mapping.length) return;
  const result = await request("/api/serial/keymap", { method: "POST", body: JSON.stringify({ mapping }) });
  renderKeyMapping(result.mapping);
  if (!quiet) toast("Key assignments saved to the controller.");
}

function renderAxisMapping(mapping = state.axisMapping) {
  const inverted = new Set(mapping?.inverted || []);
  state.axisMapping = { inverted: [...inverted], swapGroups: mapping?.swapGroups === true };
  $("#swapAxisGroups").checked = state.axisMapping.swapGroups;
  $$('[data-axis-invert]').forEach((control) => {
    control.checked = inverted.has(control.dataset.axisInvert);
    control.disabled = !state.connectedForCalibration;
  });
}

function axisMappingPayload() {
  return {
    inverted: $$('[data-axis-invert]:checked').map((control) => control.dataset.axisInvert),
    swapGroups: $("#swapAxisGroups").checked,
  };
}

async function loadAxisMapping() {
  renderAxisMapping();
  if (!state.connectedForCalibration) return;
  try {
    const result = await request("/api/serial/axis-mapping");
    renderAxisMapping(result.mapping);
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveAxisMapping({ persist = false, quiet = false } = {}) {
  if (!state.connectedForCalibration) throw new Error("Connect the controller before changing axis mapping.");
  const result = await request("/api/serial/axis-mapping", {
    method: "POST",
    body: JSON.stringify({ ...axisMappingPayload(), save: persist }),
  });
  renderAxisMapping(result.mapping);
  if (!quiet) $("#tuningStatus").textContent = persist ? "Axis mapping saved" : "Axis mapping applied live";
}

function resetKeyMapping() {
  const count = hidKeyCount();
  renderKeyMapping(Array.from({ length: count }, (_, index) => index + 1));
  $("#tuningStatus").textContent = "Default key order selected — select Apply to save";
}

async function resetCenter() {
  const button = $("#resetCenter");
  button.disabled = true;
  button.textContent = "Keep still…";
  $("#tuningStatus").textContent = "Measuring the resting position…";
  try {
    await request("/api/serial/reset-center", { method: "POST", body: "{}" });
    await request("/api/serial/command", { method: "POST", body: JSON.stringify({ mode: "40" }) });
    $("#tuningStatus").textContent = "Centre reset successfully";
    toast("Resting position reset.");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Reset centre";
  }
}

function updateTuningAvailability() {
  const connected = state.connectedForCalibration;
  $("#applyTuning").disabled = !connected;
  $("#finishTuning").disabled = !connected;
  $("#resetCenter").disabled = !connected;
  $("#resetKeyMap").disabled = !connected;
  $$(".tuning-row input, .tuning-row select, [data-key-map], #swapAxisGroups, [data-axis-invert]").forEach((control) => { control.disabled = !connected; });
  $("#tuningStatus").textContent = connected
    ? "Controller connected — adjustments apply live"
    : "Connect the controller to adjust it live";
}

async function saveTuning() {
  if (!state.connectedForCalibration) throw new Error("Reconnect the controller from Test motion before tuning.");
  $("#tuningStatus").textContent = "Applying settings…";
  const result = await request("/api/serial/tune", { method: "POST", body: JSON.stringify(tuningPayload()) });
  if (!result.ok) throw new Error(result.error || "Could not apply tuning");
  $("#tuningStatus").textContent = "Settings applied to the controller";
}

async function persistTuningChanges() {
  await saveTuning();
  await saveKeyMapping({ quiet: true });
  await saveAxisMapping({ persist: true, quiet: true });
  $("#tuningStatus").textContent = "Changes saved to the controller";
}

async function applyTuning() {
  const button = $("#applyTuning");
  button.disabled = true;
  button.textContent = "Applying…";
  try {
    await persistTuningChanges();
    toast("Tuning changes saved.");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.textContent = "Apply";
    button.disabled = !state.connectedForCalibration;
  }
}

async function finishTuning() {
  const button = $("#finishTuning");
  button.disabled = true;
  try {
    await persistTuningChanges();
    state.completed = true;
    await request("/api/setup/complete", { method: "POST", body: "{}" });
    $("#resumeTuning").hidden = false;
    await disconnectCalibration();
    showScreen(7);
  } catch (error) {
    toast(error.message, true);
    button.disabled = false;
  }
}

function bindEvents() {
  $$('[data-go]').forEach((button) => button.addEventListener("click", () => showScreen(button.dataset.go)));
  $$('[data-back]').forEach((button) => button.addEventListener("click", () => showScreen(state.currentScreen - 1)));
  $("#brandHome").addEventListener("click", (event) => { event.preventDefault(); showScreen(0); });
  $("#refreshStatus").addEventListener("click", () => refreshStatus(false));
  $("#prepareFirmware").addEventListener("click", prepareFirmware);
  $("#installFirmware").addEventListener("click", installFirmware);
  $("#connectCalibration").addEventListener("click", connectCalibration);
  $("#disconnectCalibration").addEventListener("click", disconnectCalibration);
  $("#runMotionStage").addEventListener("click", runMotionStage);
  $("#finishCalibration").addEventListener("click", continueToTuning);
  $("#tuningBack").addEventListener("click", leaveTuning);
  $("#resumeTuning").addEventListener("click", () => enterDirectTuning(0));
  $("#readyFineTune").addEventListener("click", () => enterDirectTuning(7));
  $("#toggleLiveData").addEventListener("click", () => {
    setLiveDataExpanded($("#calibrationOutput").hidden);
  });
  $("#finishTuning").addEventListener("click", finishTuning);
  $("#applyTuning").addEventListener("click", applyTuning);
  $("#recommendedTuning").addEventListener("click", async () => {
    ["translationTune", "verticalTune", "rotationTune", "stabilityTune", "curvePrecision", "curveBoost"].forEach((id) => { $(`#${id}`).value = "5"; });
    $("#curveMode").value = "adaptive";
    renderTuningLabels();
    try { await saveTuning(); } catch (error) { toast(error.message, true); }
  });
  $$(".tuning-row input").forEach((input) => {
    input.addEventListener("input", () => { renderTuningLabels(); $("#tuningStatus").textContent = "Release to apply"; });
    input.addEventListener("change", async () => { try { await saveTuning(); } catch (error) { toast(error.message, true); } });
  });
  $("#curveMode").addEventListener("change", async () => { renderTuningLabels(); try { await saveTuning(); } catch (error) { toast(error.message, true); } });
  $("#resetCenter").addEventListener("click", resetCenter);
  $("#resetKeyMap").addEventListener("click", resetKeyMapping);
  $$("#swapAxisGroups, [data-axis-invert]").forEach((control) => {
    control.addEventListener("change", async () => {
      try { await saveAxisMapping(); } catch (error) { toast(error.message, true); }
    });
  });

  $$('input[name="edition"], input[name="controllerStyleChoice"], #handedness, #baseVariant, #controlVariant, #buttonMode, #wheelAxis, #exclusiveMode')
    .forEach((element) => element.addEventListener("change", () => updateVariantUI(true)));

  const about = $("#aboutDialog");
  $("#openAbout").addEventListener("click", () => about.showModal());
  $("#closeAbout").addEventListener("click", () => about.close());
  $("#closeAboutAction").addEventListener("click", () => about.close());
  about.addEventListener("click", (event) => { if (event.target === about) about.close(); });
}

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  renderTuningLabels();
  setupMotionStages();
  try {
    const payload = await request("/api/settings");
    applySettings(payload.settings);
    $("#configPreview").textContent = payload.preview;
  } catch (error) {
    toast(error.message, true);
  }
  try {
    const setupState = await request("/api/setup/state");
    state.completed = setupState.completed === true;
  } catch (error) {
    state.completed = false;
  }
  await refreshStatus(true);
  const hashStep = state.inspectMode ? Number(window.location.hash.match(/step-(\d)/)?.[1]) : 0;
  showScreen(Number.isFinite(hashStep) && hashStep > 0 ? hashStep : 0, false);
  state.statusTimer = window.setInterval(() => {
    if ([1, 4].includes(state.currentScreen) && !state.connectedForCalibration) refreshStatus(true);
    if (state.currentScreen === 5 && !state.connectedForCalibration) prepareMotionConnection();
  }, 2200);
});
