(function () {
  "use strict";

  var source = document.getElementById("analysis-dashboard-data");
  if (!source) { return; }

  var payload;
  try { payload = JSON.parse(source.textContent); } catch (_error) { return; }

  var chartInstances = [];
  var hasChartJs = Boolean(window.Chart);
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function css(name, fallback) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback || "";
  }

  function colors() {
    return [
      css("--viz-series-1", css("--gc-accent")),
      css("--viz-series-2", css("--gc-down")),
      css("--viz-series-3", css("--gc-ok")),
      css("--viz-series-4", css("--gc-warn")),
      css("--viz-series-5", css("--gc-gutter")),
      css("--viz-series-6", css("--gc-muted"))
    ];
  }

  function finite(value) { return Number.isFinite(Number(value)); }
  function valid(items) {
    return (items || []).filter(function (item) { return finite(item.value); });
  }
  function clamp(value, low, high) { return Math.max(low, Math.min(high, value)); }
  function number(value, digits) {
    if (!finite(value)) { return "—"; }
    return Number(value).toLocaleString(undefined, {
      minimumFractionDigits: digits || 0,
      maximumFractionDigits: digits === undefined ? 1 : digits
    });
  }
  function percent(value) { return finite(value) ? number(value, 1) + "%" : "—"; }
  function isoDate(value) {
    var date = new Date(Number(value));
    return Number.isNaN(date.valueOf()) ? "—" : date.toISOString().slice(0, 10);
  }
  function safeDate(value) {
    if (!value) { return null; }
    var stamp = Date.parse(value);
    return Number.isNaN(stamp) ? null : stamp;
  }

  function canvasHost(panel) { return panel.querySelector("[data-chart-canvas]"); }
  function controlHost(panel) { return panel.querySelector("[data-chart-controls]"); }

  function clear(panel) {
    panel.hidden = false;
    controlHost(panel).replaceChildren();
    canvasHost(panel).replaceChildren();
    canvasHost(panel).classList.remove("is-tall");
  }

  function destroyPanelCharts(panel) {
    chartInstances = chartInstances.filter(function (instance) {
      if (!instance.canvas || instance.canvas.closest(".viz-panel") !== panel) { return true; }
      instance.destroy();
      return false;
    });
  }

  function clearFigure(panel) {
    destroyPanelCharts(panel);
    canvasHost(panel).replaceChildren();
    canvasHost(panel).classList.remove("is-tall");
  }

  function empty(panel, message) {
    var node = document.createElement("p");
    node.className = "viz-empty";
    node.textContent = message || "No observed values for this figure.";
    canvasHost(panel).appendChild(node);
  }

  function requireChart(panel) {
    if (hasChartJs) { return true; }
    empty(panel, "The chart renderer did not load. Exact values remain available in Data tables.");
    return false;
  }

  function makeCanvas(panel, height, minWidth, label) {
    var viewport = document.createElement("div");
    viewport.className = "viz-chart-viewport";
    var wrap = document.createElement("div");
    wrap.className = "viz-chart-wrap";
    wrap.style.height = Math.max(260, height || 340) + "px";
    if (minWidth) { wrap.style.width = "max(100%, " + minWidth + "px)"; }
    var element = document.createElement("canvas");
    element.setAttribute("role", "img");
    element.setAttribute("aria-label", label);
    wrap.appendChild(element);
    viewport.appendChild(wrap);
    canvasHost(panel).appendChild(viewport);
    return element;
  }

  function addChart(element, config) {
    chartInstances.push(new Chart(element, config));
  }

  function addSelect(panel, label, options, selected, onChange) {
    if (!options || options.length < 2) { return null; }
    var wrapper = document.createElement("label");
    wrapper.className = "viz-control";
    var text = document.createElement("span");
    text.textContent = label;
    var select = document.createElement("select");
    select.className = "field-input viz-chart-select";
    options.forEach(function (option) {
      var node = document.createElement("option");
      node.value = String(option.value);
      node.textContent = option.label;
      node.selected = String(option.value) === String(selected);
      select.appendChild(node);
    });
    select.addEventListener("change", function () { onChange(select.value); });
    wrapper.appendChild(text);
    wrapper.appendChild(select);
    controlHost(panel).appendChild(wrapper);
    return select;
  }

  function tooltipFor(unit) {
    return {
      backgroundColor: css("--gc-heading"),
      titleColor: css("--gc-surface"),
      bodyColor: css("--gc-surface"),
      borderColor: css("--gc-border-strong"),
      borderWidth: 1,
      padding: 10,
      displayColors: true,
      callbacks: {
        label: function (context) {
          var raw = context.raw || {};
          var value = finite(raw.value) ? raw.value : (finite(raw.x) ? raw.x : raw.y);
          var suffix = unit || "";
          var output = context.dataset.label + ": " + number(value, suffix === "%" ? 1 : undefined) + suffix;
          return raw.detail ? output + " · " + raw.detail : output;
        },
        afterLabel: function (context) {
          var raw = context.raw || {};
          if (finite(raw.low) && finite(raw.high)) {
            return "95% CI " + number(raw.low, 1) + "–" + number(raw.high, 1) + (unit || "");
          }
          return "";
        }
      }
    };
  }

  function baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: reduceMotion ? false : {duration: 0},
      normalized: true,
      interaction: {mode: "nearest", intersect: false},
      layout: {padding: {top: 8, right: 12, bottom: 2, left: 4}},
      plugins: {
        legend: {
          position: "bottom",
          align: "start",
          labels: {
            color: css("--gc-muted"),
            boxWidth: 9,
            boxHeight: 9,
            usePointStyle: true,
            padding: 18,
            font: {family: css("--gc-mono"), size: 10}
          }
        },
        title: {display: false},
        tooltip: tooltipFor("")
      },
      scales: {
        x: {
          grid: {color: css("--gc-border"), lineWidth: 1},
          ticks: {color: css("--gc-muted"), font: {family: css("--gc-mono"), size: 10}},
          border: {color: css("--gc-border-strong")}
        },
        y: {
          grid: {display: false},
          ticks: {color: css("--gc-text"), font: {size: 11}},
          border: {display: false}
        }
      }
    };
  }

  var errorBars = {
    id: "gcErrorBars",
    afterDatasetsDraw: function (chart, _args, options) {
      var orientation = (options && options.orientation) || "vertical";
      var ctx = chart.ctx;
      chart.data.datasets.forEach(function (dataset, datasetIndex) {
        if (dataset.errorBars === false) { return; }
        var meta = chart.getDatasetMeta(datasetIndex);
        if (meta.hidden) { return; }
        meta.data.forEach(function (element, index) {
          var raw = dataset.data[index] || {};
          if (!finite(raw.low) || !finite(raw.high) || element.skip) { return; }
          var x1;
          var x2;
          var y1;
          var y2;
          if (orientation === "horizontal") {
            x1 = chart.scales.x.getPixelForValue(raw.low);
            x2 = chart.scales.x.getPixelForValue(raw.high);
            y1 = element.y;
            y2 = element.y;
          } else {
            x1 = element.x;
            x2 = element.x;
            y1 = chart.scales.y.getPixelForValue(raw.low);
            y2 = chart.scales.y.getPixelForValue(raw.high);
          }
          ctx.save();
          ctx.strokeStyle = dataset.errorBarColor || css("--gc-muted");
          ctx.globalAlpha = 0.72;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          if (orientation === "horizontal") {
            ctx.moveTo(x1, y1 - 3);
            ctx.lineTo(x1, y1 + 3);
            ctx.moveTo(x2, y2 - 3);
            ctx.lineTo(x2, y2 + 3);
          } else {
            ctx.moveTo(x1 - 3, y1);
            ctx.lineTo(x1 + 3, y1);
            ctx.moveTo(x2 - 3, y2);
            ctx.lineTo(x2 + 3, y2);
          }
          ctx.stroke();
          ctx.restore();
        });
      });
    }
  };

  var pairedConnectors = {
    id: "gcPairedConnectors",
    beforeDatasetsDraw: function (chart) {
      if (chart.data.datasets.length < 2) { return; }
      var first = chart.getDatasetMeta(0).data;
      var second = chart.getDatasetMeta(1).data;
      var ctx = chart.ctx;
      ctx.save();
      ctx.strokeStyle = css("--gc-border-strong");
      ctx.lineWidth = 1;
      for (var index = 0; index < Math.min(first.length, second.length); index += 1) {
        if (first[index].skip || second[index].skip) { continue; }
        ctx.beginPath();
        ctx.moveTo(first[index].x, first[index].y);
        ctx.lineTo(second[index].x, second[index].y);
        ctx.stroke();
      }
      ctx.restore();
    }
  };

  var lollipopStems = {
    id: "gcLollipopStems",
    beforeDatasetsDraw: function (chart) {
      var ctx = chart.ctx;
      var origin = chart.scales.x.getPixelForValue(0);
      ctx.save();
      ctx.strokeStyle = css("--gc-border-strong");
      ctx.lineWidth = 1;
      chart.data.datasets.forEach(function (_dataset, datasetIndex) {
        chart.getDatasetMeta(datasetIndex).data.forEach(function (point) {
          if (point.skip) { return; }
          ctx.beginPath();
          ctx.moveTo(origin, point.y);
          ctx.lineTo(point.x, point.y);
          ctx.stroke();
        });
      });
      ctx.restore();
    }
  };

  var rangeConnectors = {
    id: "gcRangeConnectors",
    beforeDatasetsDraw: function (chart) {
      if (chart.data.datasets.length < 2) { return; }
      var byLabel = {};
      chart.data.datasets.forEach(function (dataset, datasetIndex) {
        var meta = chart.getDatasetMeta(datasetIndex);
        dataset.data.forEach(function (raw, index) {
          if (!byLabel[raw.y]) { byLabel[raw.y] = []; }
          if (!meta.data[index].skip) { byLabel[raw.y].push(meta.data[index]); }
        });
      });
      var ctx = chart.ctx;
      ctx.save();
      ctx.strokeStyle = css("--gc-border-strong");
      ctx.lineWidth = 1.25;
      Object.keys(byLabel).forEach(function (label) {
        if (byLabel[label].length !== 2) { return; }
        ctx.beginPath();
        ctx.moveTo(byLabel[label][0].x, byLabel[label][0].y);
        ctx.lineTo(byLabel[label][1].x, byLabel[label][1].y);
        ctx.stroke();
      });
      ctx.restore();
    }
  };

  function pointStyle(raw) { return raw && raw.small ? "triangle" : "circle"; }

  function pairedDot(chart, panel) {
    if (!requireChart(panel)) { return; }
    var datasets = (chart.datasets || []).map(function (dataset) {
      return {label: dataset.label, items: valid(dataset.items)};
    }).filter(function (dataset) { return dataset.items.length; });
    if (datasets.length < 1) { empty(panel); return; }
    var labels = datasets[0].items.map(function (item) { return item.label; });
    var byDataset = datasets.map(function (dataset) {
      var indexed = {};
      dataset.items.forEach(function (item) { indexed[item.label] = item; });
      return indexed;
    });
    var element = makeCanvas(panel, Math.max(310, labels.length * 34 + 95), 720, chart.title + ". Paired prevalence estimates with 95% confidence intervals.");
    var options = baseOptions();
    options.plugins.tooltip = tooltipFor("%");
    options.plugins.gcErrorBars = {orientation: "horizontal"};
    options.scales.x.min = 0;
    options.scales.x.suggestedMax = 10;
    options.scales.x.max = 100;
    options.scales.x.title = {display: true, text: "Observed prevalence (%)", color: css("--gc-muted"), font: {size: 10}};
    options.scales.y.type = "category";
    options.scales.y.labels = labels;
    options.scales.y.offset = true;
    options.scales.y.ticks.autoSkip = false;
    var seriesColors = colors();
    addChart(element, {
      type: "scatter",
      data: {
        datasets: datasets.map(function (dataset, index) {
          return {
            label: dataset.label,
            data: labels.map(function (label) {
              var item = byDataset[index][label];
              return item ? Object.assign({}, item, {x: item.value, y: label}) : {x: null, y: label};
            }),
            backgroundColor: seriesColors[index],
            borderColor: seriesColors[index],
            errorBarColor: seriesColors[index],
            pointRadius: index ? 5 : 4,
            pointHoverRadius: 7,
            pointStyle: function (context) { return pointStyle(context.raw); }
          };
        })
      },
      options: options,
      plugins: [pairedConnectors, errorBars]
    });
  }

  function heatmap(chart, panel) {
    var rows = (chart.rows || []).slice().sort(function (a, b) {
      return Number(b.n || 0) - Number(a.n || 0) || a.label.localeCompare(b.label);
    });
    var columns = chart.columns || [];
    if (!rows.length || !columns.length) { empty(panel); return; }
    var rowLimit = rows.length > 24 ? 24 : rows.length;
    var columnLimit = columns.length > 12 ? 12 : columns.length;

    function draw() {
      clearFigure(panel);
      var shownRows = rows.slice(0, rowLimit);
      var shownColumns = columns.slice(0, columnLimit);
      var viewport = document.createElement("div");
      viewport.className = "viz-heatmap-viewport";
      var table = document.createElement("table");
      table.className = "viz-heatmap";
      var thead = document.createElement("thead");
      var heading = document.createElement("tr");
      ["Country", "n"].concat(shownColumns).forEach(function (label, index) {
        var cell = document.createElement("th");
        cell.scope = "col";
        cell.textContent = label;
        if (index > 1) { cell.title = label; }
        heading.appendChild(cell);
      });
      thead.appendChild(heading);
      table.appendChild(thead);
      var tbody = document.createElement("tbody");
      shownRows.forEach(function (row) {
        var tr = document.createElement("tr");
        var label = document.createElement("th");
        label.scope = "row";
        label.textContent = row.label;
        if (row.code && row.code !== "??") {
          var code = document.createElement("small");
          code.textContent = row.code;
          label.appendChild(code);
        }
        tr.appendChild(label);
        var n = document.createElement("td");
        n.className = "viz-heatmap-n";
        n.textContent = number(row.n, 0);
        tr.appendChild(n);
        shownColumns.forEach(function (column) {
          var value = row.cells && row.cells[column];
          var td = document.createElement("td");
          td.className = "viz-heatmap-cell";
          if (value && finite(value.value)) {
            td.style.setProperty("--heat", String(clamp(Number(value.value) / 100, 0, 1)));
            td.textContent = number(value.value, 1);
            td.title = row.label + " · " + column + ": " + percent(value.value) + " (" + number(value.count, 0) + "/" + number(row.n, 0) + ")";
            td.setAttribute("aria-label", td.title);
          } else {
            td.classList.add("is-missing");
            td.textContent = "—";
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      viewport.appendChild(table);
      var scale = document.createElement("div");
      scale.className = "viz-heatmap-scale";
      scale.innerHTML = "<span>0%</span><i aria-hidden=\"true\"></i><span>100%</span>";
      canvasHost(panel).appendChild(viewport);
      canvasHost(panel).appendChild(scale);
    }

    addSelect(panel, "Countries", [
      {label: "Top 12 by corpus size", value: Math.min(12, rows.length)},
      {label: "Top 24 by corpus size", value: Math.min(24, rows.length)},
      {label: "All " + rows.length + " countries", value: rows.length}
    ].filter(function (option, index, all) {
      return all.findIndex(function (candidate) { return candidate.value === option.value; }) === index;
    }), rowLimit, function (value) { rowLimit = Number(value); draw(); });
    addSelect(panel, "Agents", [
      {label: "Top 8 agents", value: Math.min(8, columns.length)},
      {label: "Top 12 agents", value: Math.min(12, columns.length)},
      {label: "All " + columns.length + " agents", value: columns.length}
    ].filter(function (option, index, all) {
      return all.findIndex(function (candidate) { return candidate.value === option.value; }) === index;
    }), columnLimit, function (value) { columnLimit = Number(value); draw(); });
    draw();
  }

  function coverageHeatmap(chart, panel) {
    var dimensions = (chart.dimensions || []).filter(function (dimension) {
      return dimension.rows && dimension.rows.length;
    });
    var measures = chart.measures || [];
    if (!dimensions.length || !measures.length) { empty(panel); return; }
    var dimensionIndex = 0;
    var rowLimit = Math.min(24, dimensions[0].rows.length);
    var rowControl = null;

    function syncRowOptions() {
      if (!rowControl) { return; }
      var count = dimensions[dimensionIndex].rows.length;
      var choices = [12, 24, count].map(function (value) { return Math.min(value, count); });
      choices = choices.filter(function (value, index) { return choices.indexOf(value) === index; });
      rowControl.replaceChildren();
      choices.forEach(function (value) {
        var option = document.createElement("option");
        option.value = String(value);
        option.textContent = value === count ? "All " + count + " strata" : "Top " + value + " strata";
        rowControl.appendChild(option);
      });
      rowLimit = Math.min(24, count);
      rowControl.value = String(rowLimit);
    }

    function draw() {
      clearFigure(panel);
      var dimension = dimensions[dimensionIndex];
      var rows = dimension.rows.slice(0, rowLimit);
      var viewport = document.createElement("div");
      viewport.className = "viz-heatmap-viewport";
      var table = document.createElement("table");
      table.className = "viz-heatmap viz-coverage-heatmap";
      var thead = document.createElement("thead");
      var heading = document.createElement("tr");
      [dimension.label, "n"].concat(measures.map(function (measure) { return measure.label; })).forEach(function (text) {
        var th = document.createElement("th");
        th.scope = "col";
        th.textContent = text;
        th.title = text;
        heading.appendChild(th);
      });
      thead.appendChild(heading);
      table.appendChild(thead);
      var tbody = document.createElement("tbody");
      rows.forEach(function (row) {
        var tr = document.createElement("tr");
        var label = document.createElement("th");
        label.scope = "row";
        label.textContent = row.label;
        tr.appendChild(label);
        var n = document.createElement("td");
        n.className = "viz-heatmap-n";
        n.textContent = number(row.repos, 0);
        tr.appendChild(n);
        measures.forEach(function (measure) {
          var rate = row.coverage && row.coverage[measure.key];
          var td = document.createElement("td");
          td.className = "viz-heatmap-cell";
          if (!rate || rate.applicable === false) {
            td.classList.add("is-missing");
            td.textContent = "n/a";
            td.title = row.label + " · " + measure.label + ": " + ((rate && rate.reason) || "not selected in this run");
          } else if (finite(rate.percent)) {
            td.style.setProperty("--heat", String(clamp(Number(rate.percent) / 100, 0, 1)));
            td.textContent = number(rate.percent, 1);
            td.title = row.label + " · " + measure.label + ": " + percent(rate.percent) + " (" + number(rate.count, 0) + "/" + number(rate.eligible, 0) + ")";
          } else {
            td.classList.add("is-missing");
            td.textContent = "—";
            td.title = row.label + " · " + measure.label + ": no eligible denominator";
          }
          td.setAttribute("aria-label", td.title);
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      viewport.appendChild(table);
      canvasHost(panel).appendChild(viewport);
      var scale = document.createElement("div");
      scale.className = "viz-heatmap-scale";
      scale.innerHTML = "<span>0%</span><i aria-hidden=\"true\"></i><span>100% coverage</span>";
      canvasHost(panel).appendChild(scale);
    }

    addSelect(panel, "Dimension", dimensions.map(function (dimension, index) {
      return {label: dimension.label, value: index};
    }), dimensionIndex, function (value) {
      dimensionIndex = Number(value);
      syncRowOptions();
      draw();
    });
    rowControl = addSelect(panel, "Strata", [
      {label: "Top 12 strata", value: Math.min(12, dimensions[0].rows.length)},
      {label: "Top 24 strata", value: Math.min(24, dimensions[0].rows.length)},
      {label: "All " + dimensions[0].rows.length + " strata", value: dimensions[0].rows.length}
    ].filter(function (option, index, all) {
      return all.findIndex(function (candidate) { return candidate.value === option.value; }) === index;
    }), rowLimit, function (value) { rowLimit = Number(value); draw(); });
    draw();
  }

  function composition(chart, panel) {
    var segments = (chart.segments || []).filter(function (segment) {
      return finite(segment.value) && Number(segment.value) > 0;
    });
    if (!segments.length) { empty(panel); return; }
    var palette = colors();
    var figure = document.createElement("div");
    figure.className = "viz-composition";
    var strip = document.createElement("div");
    strip.className = "viz-composition-strip";
    strip.setAttribute("role", "img");
    strip.setAttribute("aria-label", segments.map(function (segment) {
      return segment.label + " " + percent(segment.value);
    }).join(", "));
    segments.forEach(function (segment, index) {
      var part = document.createElement("span");
      part.className = "viz-composition-part";
      part.style.width = clamp(Number(segment.value), 0, 100) + "%";
      part.style.backgroundColor = palette[index % palette.length];
      part.title = segment.label + ": " + percent(segment.value) + " · " + number(segment.count, 0) + " repos";
      if (Number(segment.value) >= 8) { part.textContent = number(segment.value, 1); }
      strip.appendChild(part);
    });
    figure.appendChild(strip);
    var legend = document.createElement("div");
    legend.className = "viz-composition-legend";
    segments.forEach(function (segment, index) {
      var item = document.createElement("div");
      item.innerHTML = "<i aria-hidden=\"true\"></i><span></span><strong></strong><small></small>";
      item.querySelector("i").style.backgroundColor = palette[index % palette.length];
      item.querySelector("span").textContent = segment.label;
      item.querySelector("strong").textContent = percent(segment.value);
      item.querySelector("small").textContent = number(segment.count, 0) + " repos";
      legend.appendChild(item);
    });
    figure.appendChild(legend);
    canvasHost(panel).appendChild(figure);
  }

  function sortedForestItems(dataset, minimumN) {
    return valid(dataset.items).filter(function (item) {
      return !minimumN || !finite(item.n) || Number(item.n) >= minimumN;
    }).sort(function (a, b) {
      if (a.label === "Unknown") { return 1; }
      if (b.label === "Unknown") { return -1; }
      return Number(b.value) - Number(a.value) || Number(b.n || 0) - Number(a.n || 0) || a.label.localeCompare(b.label);
    });
  }

  function forest(chart, panel) {
    if (!requireChart(panel)) { return; }
    var datasets = (chart.datasets || []).filter(function (dataset) { return valid(dataset.items).length; });
    if (!datasets.length) { empty(panel); return; }
    var datasetIndex = 0;
    var defaultEligible = valid(datasets[0].items).filter(function (item) { return Number(item.n) >= 10; });
    var minimumN = chart.filter_by_n && defaultEligible.length >= 3 ? 10 : 1;
    var nControl = null;

    function draw() {
      clearFigure(panel);
      var dataset = datasets[datasetIndex];
      var items = sortedForestItems(dataset, minimumN);
      if (!items.length && minimumN > 1) {
        minimumN = 1;
        if (nControl) { nControl.value = "1"; }
        items = sortedForestItems(dataset, minimumN);
      }
      if (!items.length) { empty(panel); return; }
      if (items.length > 22) { canvasHost(panel).classList.add("is-tall"); }
      var labels = items.map(function (item) { return item.label; });
      var element = makeCanvas(panel, Math.max(320, labels.length * 30 + 85), 760, chart.title + ". Point estimates and 95% confidence intervals by " + (chart.key === "country-adoption" ? "country" : "language") + ".");
      var options = baseOptions();
      options.plugins.legend.display = false;
      options.plugins.tooltip = tooltipFor(chart.unit || "%");
      options.plugins.gcErrorBars = {orientation: "horizontal"};
      options.scales.x.min = 0;
      options.scales.x.max = 100;
      options.scales.x.title = {display: true, text: dataset.label + " (%)", color: css("--gc-muted"), font: {size: 10}};
      options.scales.y.type = "category";
      options.scales.y.labels = labels;
      options.scales.y.offset = true;
      options.scales.y.ticks.autoSkip = false;
      addChart(element, {
        type: "scatter",
        data: {
          datasets: [{
            label: dataset.label,
            data: items.map(function (item) { return Object.assign({}, item, {x: item.value, y: item.label}); }),
            backgroundColor: colors()[0],
            borderColor: colors()[0],
            errorBarColor: colors()[0],
            pointRadius: 4.5,
            pointHoverRadius: 7,
            pointStyle: function (context) { return pointStyle(context.raw); }
          }]
        },
        options: options,
        plugins: [errorBars]
      });
    }

    addSelect(panel, "Measure", datasets.map(function (dataset, index) {
      return {label: dataset.label, value: index};
    }), datasetIndex, function (value) { datasetIndex = Number(value); draw(); });
    if (chart.filter_by_n) {
      var maximumN = Math.max.apply(null, datasets.reduce(function (all, dataset) {
        return all.concat(valid(dataset.items).map(function (item) { return Number(item.n) || 0; }));
      }, [1]));
      var thresholds = [1, 10, 25, 50].filter(function (value) { return value === 1 || maximumN >= value; });
      nControl = addSelect(panel, "Minimum eligible n", thresholds.map(function (value) {
        return {label: value === 1 ? "All observed strata" : "n ≥ " + value, value: value};
      }), minimumN, function (value) { minimumN = Number(value); draw(); });
    }
    draw();
  }

  function ordinalProfile(chart, panel) {
    if (!requireChart(panel)) { return; }
    var datasets = (chart.datasets || []).filter(function (dataset) { return valid(dataset.items).length; });
    if (!datasets.length) { empty(panel); return; }
    var index = 0;

    function draw() {
      clearFigure(panel);
      var dataset = datasets[index];
      var items = dataset.items || [];
      var labels = items.map(function (item) { return item.label; });
      var minWidth = Math.max(720, labels.length * 118);
      var element = makeCanvas(panel, 360, minWidth, chart.title + ". Ordered profile for " + dataset.label + ".");
      var options = baseOptions();
      options.plugins.legend.display = false;
      options.plugins.tooltip = tooltipFor(chart.unit || "%");
      options.plugins.gcErrorBars = {orientation: "vertical"};
      options.scales.x.type = "category";
      options.scales.x.labels = labels;
      options.scales.x.offset = true;
      options.scales.x.grid.display = false;
      options.scales.x.ticks.autoSkip = false;
      options.scales.x.ticks.maxRotation = 0;
      options.scales.x.ticks.callback = function (_value, tickIndex) {
        var label = labels[tickIndex] || "";
        return label.length > 15 ? label.split(/\s+/) : label;
      };
      options.scales.y.min = 0;
      options.scales.y.max = 100;
      options.scales.y.grid.display = true;
      options.scales.y.grid.color = css("--gc-border");
      options.scales.y.ticks.callback = function (value) { return value + "%"; };
      options.scales.y.title = {display: true, text: dataset.label + " (%)", color: css("--gc-muted"), font: {size: 10}};
      var breaks = chart.break_labels || [];
      addChart(element, {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            label: dataset.label,
            data: items.map(function (item) {
              return Object.assign({}, item, {x: item.label, y: item.value});
            }),
            parsing: false,
            borderColor: colors()[0],
            backgroundColor: colors()[0],
            errorBarColor: colors()[0],
            borderWidth: 1.5,
            pointRadius: 4,
            pointHoverRadius: 7,
            pointStyle: function (context) { return pointStyle(context.raw); },
            tension: 0,
            spanGaps: false,
            segment: {
              borderColor: function (context) {
                var left = labels[context.p0DataIndex];
                var right = labels[context.p1DataIndex];
                return breaks.indexOf(left) >= 0 || breaks.indexOf(right) >= 0 ? "transparent" : colors()[0];
              }
            }
          }]
        },
        options: options,
        plugins: [errorBars]
      });
    }

    addSelect(panel, "Outcome", datasets.map(function (dataset, datasetIndex) {
      return {label: dataset.label, value: datasetIndex};
    }), index, function (value) { index = Number(value); draw(); });
    draw();
  }

  function rangeTimeline(chart, panel) {
    if (!requireChart(panel)) { return; }
    var rows = (chart.rows || []).map(function (row) {
      return Object.assign({}, row, {
        repository_stamp: safeDate(row.repository_date),
        signal_stamp: safeDate(row.signal_date)
      });
    }).filter(function (row) { return row.repository_stamp !== null || row.signal_stamp !== null; });
    if (!rows.length) { empty(panel); return; }
    var labels = rows.map(function (row) { return row.label; });
    var stamps = [];
    rows.forEach(function (row) {
      if (row.repository_stamp !== null) { stamps.push(row.repository_stamp); }
      if (row.signal_stamp !== null) { stamps.push(row.signal_stamp); }
    });
    var min = Math.min.apply(null, stamps);
    var max = Math.max.apply(null, stamps);
    var padding = Math.max(86400000 * 30, (max - min) * 0.05);
    var element = makeCanvas(panel, Math.max(320, labels.length * 34 + 95), 760, chart.title + ". Earliest repository dates paired with earliest observed signal dates.");
    var options = baseOptions();
    options.plugins.tooltip = {
      backgroundColor: css("--gc-heading"),
      titleColor: css("--gc-surface"),
      bodyColor: css("--gc-surface"),
      callbacks: {
        title: function (items) { return items[0] ? items[0].raw.y : ""; },
        label: function (context) { return context.dataset.label + ": " + isoDate(context.raw.x) + " · " + context.raw.detail; }
      }
    };
    options.scales.x.type = "linear";
    options.scales.x.min = min - padding;
    options.scales.x.max = max + padding;
    options.scales.x.ticks.callback = function (value) { return isoDate(value).slice(0, 7); };
    options.scales.x.title = {display: true, text: "Calendar date (UTC)", color: css("--gc-muted"), font: {size: 10}};
    options.scales.y.type = "category";
    options.scales.y.labels = labels;
    options.scales.y.offset = true;
    options.scales.y.ticks.autoSkip = false;
    var palette = colors();
    addChart(element, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Earliest repository created",
            data: rows.filter(function (row) { return row.repository_stamp !== null; }).map(function (row) {
              return {x: row.repository_stamp, y: row.label, detail: number(row.repos, 0) + " repos"};
            }),
            backgroundColor: palette[4],
            borderColor: palette[4],
            pointStyle: "rectRot",
            pointRadius: 5,
            pointHoverRadius: 7
          },
          {
            label: "Earliest observed signal",
            data: rows.filter(function (row) { return row.signal_stamp !== null; }).map(function (row) {
              return {x: row.signal_stamp, y: row.label, detail: number(row.dated, 0) + "/" + number(row.repos, 0) + " dated"};
            }),
            backgroundColor: palette[0],
            borderColor: palette[0],
            pointStyle: "circle",
            pointRadius: 5,
            pointHoverRadius: 7
          }
        ]
      },
      options: options,
      plugins: [rangeConnectors]
    });
  }

  var percentileRanges = {
    id: "gcPercentileRanges",
    beforeDatasetsDraw: function (chart) {
      if (chart.data.datasets.length < 3) { return; }
      var first = chart.getDatasetMeta(0).data;
      var last = chart.getDatasetMeta(2).data;
      var ctx = chart.ctx;
      ctx.save();
      ctx.strokeStyle = css("--gc-border-strong");
      ctx.lineWidth = 1.5;
      for (var index = 0; index < Math.min(first.length, last.length); index += 1) {
        if (first[index].skip || last[index].skip) { continue; }
        ctx.beginPath();
        ctx.moveTo(first[index].x, first[index].y);
        ctx.lineTo(last[index].x, last[index].y);
        ctx.stroke();
      }
      ctx.restore();
    }
  };

  function percentileTimeline(chart, panel) {
    if (!requireChart(panel)) { return; }
    var rows = (chart.rows || []).map(function (row) {
      return Object.assign({}, row, {
        p0Stamp: safeDate(row.p0),
        p10Stamp: safeDate(row.p10),
        p50Stamp: safeDate(row.p50)
      });
    }).filter(function (row) { return row.p0Stamp !== null || row.p50Stamp !== null; });
    if (!rows.length) { empty(panel); return; }
    rows.sort(function (a, b) {
      return (a.p10Stamp || Infinity) - (b.p10Stamp || Infinity) || a.label.localeCompare(b.label);
    });
    var labels = rows.map(function (row) { return row.label; });
    var stamps = [];
    rows.forEach(function (row) {
      [row.p0Stamp, row.p10Stamp, row.p50Stamp].forEach(function (stamp) {
        if (stamp !== null) { stamps.push(stamp); }
      });
    });
    var min = Math.min.apply(null, stamps);
    var max = Math.max.apply(null, stamps);
    var padding = Math.max(86400000 * 30, (max - min) * 0.05);
    var element = makeCanvas(panel, Math.max(340, labels.length * 32 + 100), 820, chart.title + ". P0, P10, and median observed signal dates by agent.");
    var options = baseOptions();
    options.plugins.tooltip = {
      backgroundColor: css("--gc-heading"),
      titleColor: css("--gc-surface"),
      bodyColor: css("--gc-surface"),
      callbacks: {
        title: function (items) { return items[0] ? items[0].raw.y : ""; },
        label: function (context) {
          return context.dataset.label + ": " + isoDate(context.raw.x) + " · " + context.raw.detail;
        }
      }
    };
    options.scales.x.type = "linear";
    options.scales.x.min = min - padding;
    options.scales.x.max = max + padding;
    options.scales.x.ticks.callback = function (value) { return isoDate(value).slice(0, 7); };
    options.scales.x.title = {display: true, text: "Observed signal date (UTC)", color: css("--gc-muted"), font: {size: 10}};
    options.scales.y.type = "category";
    options.scales.y.labels = labels;
    options.scales.y.offset = true;
    options.scales.y.ticks.autoSkip = false;
    var palette = colors();
    function points(key) {
      return rows.map(function (row) {
        return {
          x: row[key],
          y: row.label,
          detail: number(row.dated, 0) + "/" + number(row.repos, 0) + " dated · " + percent(row.coverage) + " coverage"
        };
      });
    }
    addChart(element, {
      type: "scatter",
      data: {datasets: [
        {label: "P0 (minimum)", data: points("p0Stamp"), backgroundColor: palette[4], borderColor: palette[4], pointStyle: "rectRot", pointRadius: 4},
        {label: "P10", data: points("p10Stamp"), backgroundColor: palette[0], borderColor: palette[0], pointStyle: "circle", pointRadius: 5},
        {label: "P50 (median)", data: points("p50Stamp"), backgroundColor: palette[1], borderColor: palette[1], pointStyle: "triangle", pointRadius: 5}
      ]},
      options: options,
      plugins: [percentileRanges]
    });
  }

  function channelIndex(channel) {
    var known = ["file", "branch", "commit_trailer", "author", "label", "issue"];
    var index = known.indexOf(channel);
    return index < 0 ? known.length - 1 : index;
  }

  function lollipop(chart, panel) {
    if (!requireChart(panel)) { return; }
    var datasets = (chart.datasets || []).filter(function (dataset) { return valid(dataset.items).length; });
    if (!datasets.length) { empty(panel); return; }
    var selected = datasets.reduce(function (best, dataset, index) {
      var total = valid(dataset.items).reduce(function (sum, item) { return sum + Number(item.value); }, 0);
      return total > best.total ? {index: index, total: total} : best;
    }, {index: 0, total: -1}).index;

    function draw() {
      clearFigure(panel);
      var items = valid(datasets[selected].items).sort(function (a, b) { return Number(b.value) - Number(a.value); });
      var labels = items.map(function (item) { return item.label; });
      var groups = [];
      items.forEach(function (item) {
        if (groups.indexOf(item.channel || "other") < 0) { groups.push(item.channel || "other"); }
      });
      var element = makeCanvas(panel, Math.max(300, labels.length * 42 + 95), 720, chart.title + " for " + datasets[selected].label + ". Repository counts by fingerprint.");
      var options = baseOptions();
      options.plugins.tooltip = tooltipFor(chart.unit || "");
      options.scales.x.min = 0;
      options.scales.x.ticks.precision = 0;
      options.scales.x.title = {display: true, text: "Repositories with fingerprint", color: css("--gc-muted"), font: {size: 10}};
      options.scales.y.type = "category";
      options.scales.y.labels = labels;
      options.scales.y.offset = true;
      options.scales.y.ticks.autoSkip = false;
      var palette = colors();
      addChart(element, {
        type: "scatter",
        data: {
          datasets: groups.map(function (group) {
            var color = palette[channelIndex(group) % palette.length];
            return {
              label: group.replace(/_/g, " "),
              data: items.filter(function (item) { return (item.channel || "other") === group; }).map(function (item) {
                return Object.assign({}, item, {x: item.value, y: item.label});
              }),
              backgroundColor: color,
              borderColor: color,
              pointRadius: 5,
              pointHoverRadius: 8
            };
          })
        },
        options: options,
        plugins: [lollipopStems]
      });
    }

    addSelect(panel, "Agent", datasets.map(function (dataset, index) {
      return {label: dataset.label, value: index};
    }), selected, function (value) { selected = Number(value); draw(); });
    draw();
  }

  function regression(points) {
    var fit = points.filter(function (point) { return point.in_fit && Number(point.x) > 0 && finite(point.y); });
    if (fit.length < 2) { return null; }
    var xs = fit.map(function (point) { return Math.log10(Number(point.x)); });
    var ys = fit.map(function (point) { return Number(point.y); });
    var meanX = xs.reduce(function (sum, value) { return sum + value; }, 0) / xs.length;
    var meanY = ys.reduce(function (sum, value) { return sum + value; }, 0) / ys.length;
    var denominator = xs.reduce(function (sum, value) { return sum + Math.pow(value - meanX, 2); }, 0);
    if (!denominator) { return null; }
    var slope = xs.reduce(function (sum, value, index) {
      return sum + (value - meanX) * (ys[index] - meanY);
    }, 0) / denominator;
    var intercept = meanY - slope * meanX;
    var low = Math.min.apply(null, fit.map(function (point) { return Number(point.x); }));
    var high = Math.max.apply(null, fit.map(function (point) { return Number(point.x); }));
    return [
      {x: low, y: clamp(intercept + slope * Math.log10(low), 0, 100)},
      {x: high, y: clamp(intercept + slope * Math.log10(high), 0, 100)}
    ];
  }

  function scatterRegression(chart, panel) {
    if (!requireChart(panel)) { return; }
    var points = (chart.points || []).filter(function (point) {
      return Number(point.x) > 0 && finite(point.y);
    });
    if (!points.length) { empty(panel); return; }
    var groups = [];
    points.forEach(function (point) {
      var group = point.group || "Unknown";
      if (groups.indexOf(group) < 0) { groups.push(group); }
    });
    var maxN = Math.max.apply(null, points.map(function (point) { return Number(point.n) || 1; }));
    var line = regression(points);
    var palette = colors();
    var pointShapes = ["circle", "rectRot", "triangle", "rectRounded", "crossRot", "star"];
    var datasets = groups.map(function (group, index) {
      var color = palette[index % palette.length];
      return {
        type: "bubble",
        label: group,
        data: points.filter(function (point) { return (point.group || "Unknown") === group; }).map(function (point) {
          return Object.assign({}, point, {
            r: 3.5 + Math.sqrt((Number(point.n) || 1) / maxN) * 8,
            value: point.y,
            detail: number(point.count, 0) + "/" + number(point.n, 0) + " · GDP year " + (point.year || "—")
          });
        }),
        backgroundColor: color,
        borderColor: function (context) {
          return context.raw && context.raw.influential ? css("--gc-heading") : css("--gc-surface");
        },
        borderWidth: function (context) { return context.raw && context.raw.influential ? 2.5 : 1.5; },
        pointStyle: pointShapes[index % pointShapes.length],
        errorBarColor: color
      };
    });
    if (line) {
      datasets.push({
        type: "line",
        label: "Unweighted OLS fit",
        data: line,
        borderColor: css("--gc-heading"),
        backgroundColor: css("--gc-heading"),
        borderWidth: 1.5,
        borderDash: [5, 4],
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false,
        errorBars: false
      });
    }
    var element = makeCanvas(panel, 480, 760, chart.title + ". GDP per capita on a logarithmic scale against adoption, with an ordinary least squares fit.");
    var options = baseOptions();
    options.plugins.tooltip = {
      backgroundColor: css("--gc-heading"),
      titleColor: css("--gc-surface"),
      bodyColor: css("--gc-surface"),
      callbacks: {
        title: function (items) { return items[0] && items[0].raw.label ? items[0].raw.label : items[0].dataset.label; },
        label: function (context) {
          if (!context.raw.label) { return context.dataset.label; }
          return "$" + number(context.raw.x, 0) + " GDP pc · " + percent(context.raw.y) + " · " + context.raw.detail;
        },
        afterLabel: function (context) {
          if (!context.raw.label) { return ""; }
          var interval = finite(context.raw.low) && finite(context.raw.high) ? "95% CI " + number(context.raw.low, 1) + "–" + number(context.raw.high, 1) + "%" : "";
          var fitLabel = context.raw.in_fit ? " · included in fit" : " · below fit threshold";
          var influence = context.raw.influential ? " · influential by Cook's distance" : "";
          return interval + fitLabel + influence;
        }
      }
    };
    options.plugins.gcErrorBars = {orientation: "vertical"};
    options.scales.x.type = "logarithmic";
    options.scales.x.title = {display: true, text: "GDP per capita (USD, log scale)", color: css("--gc-muted"), font: {size: 10}};
    options.scales.x.ticks.callback = function (value) { return "$" + Number(value).toLocaleString(); };
    options.scales.y.min = 0;
    options.scales.y.max = 100;
    options.scales.y.grid.display = true;
    options.scales.y.grid.color = css("--gc-border");
    options.scales.y.ticks.callback = function (value) { return value + "%"; };
    options.scales.y.title = {display: true, text: "Observed adoption (%)", color: css("--gc-muted"), font: {size: 10}};
    addChart(element, {type: "bubble", data: {datasets: datasets}, options: options, plugins: [errorBars]});
  }

  function ecdf(chart, panel) {
    if (!requireChart(panel)) { return; }
    var series = (chart.series || []).filter(function (item) {
      return item.points && item.points.some(function (point) {
        return finite(point.intensity) && finite(point.cumulative);
      });
    });
    if (!series.length && chart.points && chart.points.length) {
      series = [{key: "overall", label: "All recent adopters", points: chart.points}];
    }
    if (!series.length) { empty(panel); return; }
    var selected = 0;

    function draw() {
      clearFigure(panel);
      var population = series[selected];
      var points = population.points.filter(function (point) {
        return finite(point.intensity) && finite(point.cumulative);
      });
      var element = makeCanvas(panel, 390, 760, chart.title + " for " + population.label + ". Empirical cumulative share of recent adopters by commit intensity.");
      var options = baseOptions();
      options.plugins.legend.display = false;
      options.plugins.tooltip = {
        backgroundColor: css("--gc-heading"),
        titleColor: css("--gc-surface"),
        bodyColor: css("--gc-surface"),
        callbacks: {
          title: function (items) { return items[0] ? percent(items[0].raw.x) + " intensity" : ""; },
          label: function (context) { return percent(context.raw.y) + " of recent adopters at or below this intensity"; }
        }
      };
      options.scales.x.type = "linear";
      options.scales.x.min = 0;
      options.scales.x.max = 100;
      options.scales.x.grid.display = true;
      options.scales.x.title = {display: true, text: "Eligible commits attributed to an agent (%)", color: css("--gc-muted"), font: {size: 10}};
      options.scales.x.ticks.callback = function (value) { return value + "%"; };
      options.scales.y.min = 0;
      options.scales.y.max = 100;
      options.scales.y.grid.display = true;
      options.scales.y.grid.color = css("--gc-border");
      options.scales.y.title = {display: true, text: "Cumulative share of recent adopters (%)", color: css("--gc-muted"), font: {size: 10}};
      options.scales.y.ticks.callback = function (value) { return value + "%"; };
      addChart(element, {
        type: "line",
        data: {datasets: [{
          label: population.label,
          data: points.map(function (point) { return {x: point.intensity, y: point.cumulative}; }),
          parsing: false,
          borderColor: colors()[0],
          backgroundColor: colors()[0],
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          stepped: "after",
          fill: false
        }]},
        options: options
      });
    }

    addSelect(panel, "Population", series.map(function (item, index) {
      return {label: item.label, value: index};
    }), selected, function (value) { selected = Number(value); draw(); });
    draw();
  }

  function coUse(chart, panel) {
    var repository = chart.repositories || {};
    var repositoryBands = (repository.bands || []).filter(function (row) {
      return row.share_detected && finite(row.share_detected.percent);
    });
    var owners = chart.owners || [];
    if (!repositoryBands.length && !owners.length) { empty(panel); return; }
    var accountIndex = 0;
    var bandIndex = 0;

    function draw() {
      clearFigure(panel);
      var layout = document.createElement("div");
      layout.className = "viz-co-use";
      var repositoryFigure = document.createElement("section");
      repositoryFigure.className = "viz-co-use-repositories";
      var repositoryHeading = document.createElement("h3");
      repositoryHeading.textContent = "Distinct agents per detected repository";
      repositoryFigure.appendChild(repositoryHeading);
      var strip = document.createElement("div");
      strip.className = "viz-composition-strip";
      strip.setAttribute("role", "img");
      strip.setAttribute("aria-label", repositoryBands.map(function (row) {
        return row.band + " agents: " + percent(row.share_detected.percent);
      }).join(", "));
      var palette = colors();
      repositoryBands.forEach(function (row, index) {
        var segment = document.createElement("span");
        segment.className = "viz-composition-part";
        segment.style.width = clamp(Number(row.share_detected.percent), 0, 100) + "%";
        segment.style.backgroundColor = palette[index % palette.length];
        segment.title = row.band + " agents · " + number(row.repos, 0) + " repositories · " + percent(row.share_detected.percent);
        if (Number(row.share_detected.percent) >= 8) { segment.textContent = row.band; }
        strip.appendChild(segment);
      });
      repositoryFigure.appendChild(strip);
      var legend = document.createElement("div");
      legend.className = "viz-composition-legend";
      repositoryBands.forEach(function (row, index) {
        var item = document.createElement("div");
        var swatch = document.createElement("i");
        swatch.setAttribute("aria-hidden", "true");
        swatch.style.backgroundColor = palette[index % palette.length];
        var label = document.createElement("span");
        label.textContent = row.band + " agents";
        var share = document.createElement("strong");
        share.textContent = percent(row.share_detected.percent);
        var count = document.createElement("small");
        count.textContent = number(row.repos, 0) + " repos";
        item.appendChild(swatch);
        item.appendChild(label);
        item.appendChild(share);
        item.appendChild(count);
        legend.appendChild(item);
      });
      repositoryFigure.appendChild(legend);
      layout.appendChild(repositoryFigure);

      var ownerFigure = document.createElement("section");
      ownerFigure.className = "viz-co-use-owners";
      var owner = owners[accountIndex];
      var band = owner && owner.bands ? owner.bands[bandIndex] : null;
      var ownerHeading = document.createElement("div");
      ownerHeading.className = "viz-co-use-owner-head";
      var title = document.createElement("h3");
      title.textContent = (owner ? owner.account_type : "Owner") + " exact agent sets · " + (band ? band.band : "—") + " agents";
      var summary = document.createElement("p");
      summary.textContent = owner ? number(owner.owners_with_agents, 0) + " owners with an observed agent · " + number(owner.owners_without_agents, 0) + " with none" : "No owner data";
      ownerHeading.appendChild(title);
      ownerHeading.appendChild(summary);
      ownerFigure.appendChild(ownerHeading);
      var rankings = band ? (band.rankings || []).slice(0, 20) : [];
      if (!rankings.length) {
        var noRows = document.createElement("p");
        noRows.className = "viz-empty";
        noRows.textContent = "No owners fall in this multiplicity band.";
        ownerFigure.appendChild(noRows);
      } else {
        var table = document.createElement("table");
        table.className = "viz-rank-table";
        var thead = document.createElement("thead");
        var heading = document.createElement("tr");
        ["Rank", "Exact agent set", "Owners", "Within band"].forEach(function (label) {
          var th = document.createElement("th");
          th.scope = "col";
          th.textContent = label;
          heading.appendChild(th);
        });
        thead.appendChild(heading);
        table.appendChild(thead);
        var tbody = document.createElement("tbody");
        rankings.forEach(function (row, index) {
          var tr = document.createElement("tr");
          [String(index + 1), row.set_key, number(row.count, 0), percent(row.share_in_band)].forEach(function (value, cellIndex) {
            var cell = document.createElement(cellIndex === 1 ? "th" : "td");
            if (cellIndex === 1) { cell.scope = "row"; }
            cell.textContent = value;
            tr.appendChild(cell);
          });
          tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        ownerFigure.appendChild(table);
        if (band.rankings.length > rankings.length) {
          var remainder = document.createElement("p");
          remainder.className = "viz-table-note";
          remainder.textContent = "Showing 20 of " + number(band.rankings.length, 0) + " exact sets. Data tables contain the full ranking.";
          ownerFigure.appendChild(remainder);
        }
      }
      layout.appendChild(ownerFigure);
      canvasHost(panel).appendChild(layout);
    }

    addSelect(panel, "Account", owners.map(function (owner, index) {
      return {label: owner.account_type, value: index};
    }), accountIndex, function (value) { accountIndex = Number(value); draw(); });
    var labels = owners.length && owners[0].bands ? owners[0].bands : [];
    addSelect(panel, "Owner agent count", labels.map(function (band, index) {
      return {label: band.band + " agents", value: index};
    }), bandIndex, function (value) { bandIndex = Number(value); draw(); });
    draw();
  }

  function render() {
    chartInstances.forEach(function (instance) { instance.destroy(); });
    chartInstances = [];
    (payload.charts || []).forEach(function (chart) {
      var panel = document.querySelector('[data-chart-key="' + CSS.escape(chart.key) + '"]');
      if (!panel) { return; }
      clear(panel);
      if (chart.type === "paired_dot") { pairedDot(chart, panel); }
      else if (chart.type === "heatmap") { heatmap(chart, panel); }
      else if (chart.type === "coverage_heatmap") { coverageHeatmap(chart, panel); }
      else if (chart.type === "composition") { composition(chart, panel); }
      else if (chart.type === "forest") { forest(chart, panel); }
      else if (chart.type === "ordinal_profile") { ordinalProfile(chart, panel); }
      else if (chart.type === "range_timeline") { rangeTimeline(chart, panel); }
      else if (chart.type === "percentile_timeline") { percentileTimeline(chart, panel); }
      else if (chart.type === "lollipop") { lollipop(chart, panel); }
      else if (chart.type === "scatter_regression") { scatterRegression(chart, panel); }
      else if (chart.type === "ecdf") { ecdf(chart, panel); }
      else if (chart.type === "co_use") { coUse(chart, panel); }
      else { empty(panel, "No renderer is available for this figure."); }
    });
  }

  render();
  new MutationObserver(function (changes) {
    if (changes.some(function (change) { return change.attributeName === "data-theme"; })) { render(); }
  }).observe(document.documentElement, {attributes: true});
})();
