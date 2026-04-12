(function registerPywebviewBridge(globalObject) {
  const readyCallbacks = [];
  const stateObserversByKey = new Map();
  let isReady = false;

  function flushReadyCallbacks() {
    while (readyCallbacks.length > 0) {
      const callback = readyCallbacks.shift();
      if (typeof callback === "function") {
        callback();
      }
    }
  }

  function markReady() {
    if (!globalObject.pywebview || !globalObject.pywebview.api) {
      return;
    }

    isReady = true;
    flushReadyCallbacks();
  }

  function onReady(callback) {
    if (isReady) {
      callback();
      return;
    }

    readyCallbacks.push(callback);
    markReady();
  }

  function emitBackendEvent(eventName, payload) {
    if (
      globalObject.pywebview &&
      globalObject.pywebview.api &&
      typeof globalObject.pywebview.api.emit_event === "function"
    ) {
      return globalObject.pywebview.api.emit_event(eventName, payload || {});
    }

    return Promise.resolve(null);
  }

  function getState(key, fallbackValue) {
    if (
      !globalObject.pywebview ||
      !globalObject.pywebview.api ||
      typeof globalObject.pywebview.api.get_state !== "function"
    ) {
      return Promise.resolve(fallbackValue);
    }

    return globalObject.pywebview.api.get_state(key).then(function (value) {
      return value === undefined || value === null ? fallbackValue : value;
    });
  }

  function observeState(key, callback, fallbackValue) {
    const observerKey = String(key || "");
    const observerEntry = {
      callback: callback,
      fallbackValue: fallbackValue,
      lastSerialized: null,
    };

    if (!stateObserversByKey.has(observerKey)) {
      stateObserversByKey.set(observerKey, new Set());
    }

    stateObserversByKey.get(observerKey).add(observerEntry);

    onReady(function () {
      getState(observerKey, fallbackValue)
        .then(function (value) {
          applyStateValue(observerEntry, value);
        })
        .catch(function () {
          applyStateValue(observerEntry, fallbackValue);
        });
    });

    return function unsubscribe() {
      const observers = stateObserversByKey.get(observerKey);
      if (!observers) {
        return;
      }

      observers.delete(observerEntry);
      if (observers.size === 0) {
        stateObserversByKey.delete(observerKey);
      }
    };
  }

  function applyStateValue(observerEntry, value) {
    const normalizedValue =
      value === undefined || value === null ? observerEntry.fallbackValue : value;
    const serializedValue = JSON.stringify(normalizedValue);

    if (serializedValue === observerEntry.lastSerialized) {
      return;
    }

    observerEntry.lastSerialized = serializedValue;
    observerEntry.callback(normalizedValue);
  }

  function deliverStateUpdate(key, value) {
    const observerKey = String(key || "");
    const observers = stateObserversByKey.get(observerKey);

    if (!observers) {
      return;
    }

    observers.forEach(function (observerEntry) {
      applyStateValue(observerEntry, value);
    });
  }

  globalObject.addEventListener("pywebviewready", markReady);
  markReady();

  globalObject.appBridge = {
    __deliverStateUpdate: deliverStateUpdate,
    emitBackendEvent: emitBackendEvent,
    getState: getState,
    observeState: observeState,
    onReady: onReady,
  };
})(window);
