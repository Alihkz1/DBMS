let colCount = 0;

function documentById(id) {
  return document.getElementById(id);
}

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
  documentById("columns").appendChild(div);
  div.querySelector(".removeCol").onclick = () => div.remove();
}

function fetchAllTables() {
  // table select
  fetch("/tables")
    .then((r) => r.json())
    .then((response) => {
      let sel = documentById("tables");
      sel.innerHTML = "";
      response.tables.forEach((t) => {
        let opt = document.createElement("option");
        opt.value = t;
        opt.text = t;
        sel.appendChild(opt);
      });
      loadData();
    });
}

function loadData() {
  // load selected table data
  let table = documentById("tables").value;
  if (!table) return;
  fetch("/schema/" + table)
    .then((r) => r.json())
    .then((sch) => {
      let insertArea = documentById("insertArea");
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

      // READ
      fetch("/data/" + table)
        .then((r) => r.json())
        .then((tableDataResponse) => {
          let dataArea = documentById("dataArea");
          dataArea.innerHTML = "";
          if (tableDataResponse.rows.length == 0) {
            dataArea.innerHTML =
              "<p style='background:red;padding: 10px 5px; text-align:center; color: white '>رکوردی وجود ندارد</p>";
            return;
          }
          let tbl = document.createElement("table");
          let tr = document.createElement("tr");
          tr.innerHTML =
            "<th>#</th>" +
            tableDataResponse.schema.columns
              .map((c) => "<th>" + c.name + "</th>")
              .join("") +
            "<th>عملیات</th>";
          tbl.appendChild(tr);
          tableDataResponse.rows.forEach((rw, index) => {
            let tr = document.createElement("tr");
            tr.dataset.key = index;
            tr.innerHTML =
              "<td>" +
              (index + 1) +
              "</td>" +
              tableDataResponse.schema.columns
                .map((c) => "<td>" + (rw[c.name] || "") + "</td>")
                .join("") +
              `<td><button class='editBtn' style='margin:0 5px'>ویرایش</button><button onclick='deleteRowByKey("${table}","${index}")'>حذف</button></td>`;
            tbl.appendChild(tr);
          });
          dataArea.appendChild(tbl);

          // EDIT
          tbl.querySelectorAll(".editBtn").forEach((btn) => {
            btn.onclick = () => {
              let tr = btn.parentNode.parentNode;
              let key = tr.dataset.key;
              tr.querySelectorAll("td").forEach((td, i) => {
                if (i > 0 && i <= tableDataResponse.schema.columns.length) {
                  let val = td.textContent;
                  td.innerHTML = `<input type="text" value="${val}">`;
                }
              });
              btn.textContent = "ذخیره";
              btn.onclick = () => {
                let inputs = tr.querySelectorAll("input");
                let payload = {};
                tableDataResponse.schema.columns.forEach((c, i) => {
                  payload[c.name] = inputs[i].value;
                });
                fetch("/update/" + table + "/" + key + 1, {
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

function deleteRowByKey(table, key) {
  fetch("/delete/" + table + "/" + (key + 1), { method: "DELETE" })
    .then((r) => r.json())
    .then((res) => {
      if (res.ok) loadData();
    });
}

window.onload = () => {
  documentById("addCol").onclick = addColumnRow;
  documentById("createTableForm").onsubmit = (e) => {
    e.preventDefault();
    let table = documentById("tableName").value;
    let cols = [];
    documentById("columns")
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
          fetchAllTables();
          documentById("tableName").value = "";
          documentById("columns").innerHTML = "";
          colCount = 0;
        }
      });
  };
  documentById("tables").onchange = loadData;
  fetchAllTables();
};
