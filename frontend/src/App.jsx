// VayuLens app shell. Composes the four feature areas.
// Components are intentionally empty stubs for now.
import MapView from "./components/map/MapView.jsx";
import ForecastSlider from "./components/forecast/ForecastSlider.jsx";
import WhatIfPanel from "./components/whatif/WhatIfPanel.jsx";
import ChatPanel from "./components/chat/ChatPanel.jsx";

export default function App() {
  return (
    <div className="app">
      <h1>VayuLens</h1>
      <MapView />
      <ForecastSlider />
      <WhatIfPanel />
      <ChatPanel />
    </div>
  );
}
