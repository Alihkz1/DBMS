function $(id) {
  return document.getElementById(id);
}
let colCount = 0;
function addColumnRow() {
  colCount++;
  let div = document.createElement("div");
  div.className = "colRow";
  div.innerHTML = `<input type="text" placeholder="نام ستون" data-index="${colCount}" required>
    <select>
        <option value="TEXT">TEXT</option>
        <option value="INTEGER">INTEGER</option>
    </select>
    <button type="button" class="removeCol">x</button>`;
  $("columns").appendChild(div);
  div.querySelector(".removeCol").onclick = () => div.remove();
}

function fetchTables() {
  fetch("/tables")
    .then((r) => r.json())
    .then((d) => {
      let sel = $("tables");
      sel.innerHTML = "";
      d.tables.forEach((t) => {
        let opt = document.createElement("option");
        opt.value = t;
        opt.text = t;
        sel.appendChild(opt);
      });
      loadData();
    });
}

function loadData() {
  let table = $("tables").value;
  if (!table) return;
  fetch("/schema/" + table)
    .then((r) => r.json())
    .then((sch) => {
      let insertArea = $("insertArea");
      insertArea.innerHTML = "";
      let title = document.createElement("div");
      title.innerHTML = "در این قسمت میتوانید رکورد جدید اضافه کنید";
      title.classList.add("add-title");
      insertArea.appendChild(title);
      let form = document.createElement("form");
      form.id = "insertForm";
      sch.columns.forEach((c) => {
        let div = document.createElement("div");
        div.className = "row";
        div.innerHTML = `<label>${c.name}</label><input type="text" name="${c.name}">`;
        form.appendChild(div);
      });
      let btn = document.createElement("button");
      btn.type = "submit";
      btn.textContent = "افزودن رکورد";
      form.appendChild(btn);
      insertArea.appendChild(form);
      form.onsubmit = (e) => {
        e.preventDefault();
        let data = {};
        sch.columns.forEach((c) => {
          data[c.name] = form[c.name].value;
        });
        fetch("/insert/" + table, {
          method: "POST",
          body: JSON.stringify(data),
        })
          .then((r) => r.json())
          .then((res) => {
            if (res.ok) {
              loadData();
            }
          });
      };

      fetch("/data/" + table)
        .then((r) => r.json())
        .then((d) => {
          let da = $("dataArea");
          da.innerHTML = "";
          if (d.rows.length == 0) {
            da.innerHTML = "<p>رکوردی وجود ندارد</p>";
            return;
          }
          let tbl = document.createElement("table");
          let tr = document.createElement("tr");
          tr.innerHTML =
            "<th>#</th>" +
            d.columns.map((c) => "<th>" + c + "</th>").join("") +
            "<th>عملیات</th>";
          tbl.appendChild(tr);
          d.rows.forEach((rw) => {
            let tr = document.createElement("tr");
            tr.dataset.key = rw["__key__"];
            tr.innerHTML =
              "<td>" +
              rw["__key__"] +
              "</td>" +
              d.columns.map((c) => "<td>" + (rw[c] || "") + "</td>").join("") +
              `<td><button class='editBtn' style='margin:0 5px'>ویرایش</button><button onclick='delRow("${table}","${rw["__key__"]}")'>حذف</button></td>`;
            tbl.appendChild(tr);
          });
          da.appendChild(tbl);

          tbl.querySelectorAll(".editBtn").forEach((btn) => {
            btn.onclick = () => {
              let tr = btn.parentNode.parentNode;
              let key = tr.dataset.key;
              tr.querySelectorAll("td").forEach((td, i) => {
                if (i > 0 && i <= d.columns.length) {
                  let val = td.textContent;
                  td.innerHTML = `<input type="text" value="${val}">`;
                }
              });
              btn.textContent = "ذخیره";
              btn.onclick = () => {
                let inputs = tr.querySelectorAll("input");
                let payload = {};
                d.columns.forEach((c, i) => {
                  payload[c] = inputs[i].value;
                });
                fetch("/update/" + table + "/" + key, {
                  method: "POST",
                  body: JSON.stringify(payload),
                  headers: { "Content-Type": "application/json" },
                })
                  .then((r) => r.json())
                  .then((res) => {
                    if (res.ok) loadData();
                  });
              };
            };
          });
        });
    });
}

function delRow(table, key) {
  fetch("/delete/" + table + "/" + key, { method: "DELETE" })
    .then((r) => r.json())
    .then((res) => {
      if (res.ok) loadData();
    });
}

window.onload = () => {
  $("addCol").onclick = addColumnRow;
  $("createTableForm").onsubmit = (e) => {
    e.preventDefault();
    let table = $("tableName").value;
    let cols = [];
    $("columns")
      .querySelectorAll(".colRow")
      .forEach((row) => {
        let name = row.querySelector("input").value;
        let type = row.querySelector("select").value;
        if (name) cols.push({ name, type });
      });
    fetch("/create_table", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ table, columns: cols, auto_id: false }),
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.ok) {
          fetchTables();
          $("tableName").value = "";
          $("columns").innerHTML = "";
          colCount = 0;
        }
      });
  };
  $("tables").onchange = loadData;
  fetchTables();
};
