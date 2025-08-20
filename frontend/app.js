// شمارنده ستون‌ها برای فرم ایجاد جدول
let colCount = 0;

// تابع کمکی برای گرفتن المنت با id
function documentById(id) {
  return document.getElementById(id);
}

// وقتی صفحه لود شد
window.onload = () => {
  // دکمه اضافه کردن ستون جدید
  documentById("addCol").onclick = defineNewColumnToTable;

  // فرم ایجاد جدول
  documentById("createTableForm").onsubmit = (e) => {
    e.preventDefault(); // جلوگیری از رفرش صفحه
    let table = documentById("tableName").value; // نام جدول
    let cols = []; // آرایه ستون‌ها

    // گرفتن همه ستون‌های تعریف شده در فرم
    documentById("columns")
      .querySelectorAll(".colRow")
      .forEach((row) => {
        let name = row.querySelector("input").value; // نام ستون
        let type = row.querySelector("select").value; // نوع ستون
        if (name) cols.push({ name, type }); // اضافه کردن ستون به آرایه
      });

    // ارسال درخواست ایجاد جدول به سرور
    fetch("/create_table", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ table, columns: cols, auto_id: true }),
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.ok) {
          fetchAllTables(); // بارگذاری دوباره لیست جدول‌ها
          documentById("tableName").value = ""; // پاک کردن فیلد نام جدول
          documentById("columns").innerHTML = ""; // پاک کردن فرم ستون‌ها
          colCount = 0; // بازنشانی شمارنده ستون‌ها
        }
      });
  };

  // هنگام تغییر جدول انتخاب شده
  documentById("tables").onchange = retrieveTableData;

  // بارگذاری اولیه همه جدول‌ها
  fetchAllTables();
};

// تابع برای بارگذاری لیست همه جدول‌ها
function fetchAllTables() {
  fetch("/tables")
    .then((r) => r.json())
    .then((response) => {
      let sel = documentById("tables");
      sel.innerHTML = ""; // پاک کردن لیست قبلی
      // اضافه کردن هر جدول به select
      response.tables.forEach((t) => {
        let opt = document.createElement("option");
        opt.value = t;
        opt.text = t;
        sel.appendChild(opt);
      });
      retrieveTableData(); // بارگذاری داده‌های جدول انتخاب شده
    });
}

// تابع بارگذاری داده‌های جدول انتخاب شده
function retrieveTableData() {
  let table = documentById("tables").value; // جدول انتخاب شده
  if (!table) return;

  // گرفتن اسکیمای جدول از سرور
  fetch("/schema/" + table)
    .then((r) => r.json())
    .then((sch) => {
      let insertArea = documentById("insertArea");
      insertArea.innerHTML = ""; // پاک کردن منطقه اضافه کردن رکورد

      // عنوان فرم اضافه کردن رکورد جدید
      let title = document.createElement("div");
      title.innerHTML = "در این قسمت میتوانید رکورد جدید اضافه کنید";
      title.classList.add("add-title");
      insertArea.appendChild(title);

      // ایجاد فرم اضافه کردن رکورد
      let form = document.createElement("form");
      form.id = "insertForm";

      // ایجاد ورودی برای هر ستون
      sch.columns.forEach((c) => {
        let div = document.createElement("div");
        div.className = "row";
        div.innerHTML = `<label>${c.name}</label><input type="text" name="${c.name}">`;
        form.appendChild(div);
      });

      // دکمه ارسال رکورد جدید
      let btn = document.createElement("button");
      btn.type = "submit";
      btn.textContent = "افزودن رکورد";
      form.appendChild(btn);
      insertArea.appendChild(form);

      // ارسال رکورد جدید به سرور
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
            if (res.ok) retrieveTableData(); // بارگذاری دوباره داده‌ها
          });
      };

      // READ - نمایش داده‌ها
      fetch("/data/" + table)
        .then((r) => r.json())
        .then((tableDataResponse) => {
          let dataArea = documentById("dataArea");
          dataArea.innerHTML = "";

          // اگر رکوردی وجود نداشته باشد
          if (tableDataResponse.rows.length == 0) {
            dataArea.innerHTML =
              "<p style='background:red;padding: 10px 5px; text-align:center; color: white '>رکوردی وجود ندارد</p>";
            return;
          }

          // ایجاد جدول HTML
          let tbl = document.createElement("table");
          let tr = document.createElement("tr");

          // سرستون‌ها
          tr.innerHTML =
            "<th>#</th>" +
            tableDataResponse.schema.columns
              .map((c) => "<th>" + c.name + "</th>")
              .join("") +
            "<th>عملیات</th>";
          tbl.appendChild(tr);

          // پر کردن داده‌ها
          tableDataResponse.rows.forEach((rw, index) => {
            let tr = document.createElement("tr");
            tr.dataset.key = index; // ایندکس در آرایه
            tr.dataset.rowid = rw.rowid; // ذخیره rowid واقعی
            tr.innerHTML =
              "<td>" +
              (index + 1) +
              "</td>" +
              tableDataResponse.schema.columns
                .map((c) => "<td>" + (rw[c.name] || "") + "</td>")
                .join("") +
              `<td>
                <button class='editBtn' style='margin:0 5px'>ویرایش</button>
                <button onclick='deleteRowByRowIndex("${table}","${rw.rowid}")'>حذف</button>
              </td>`;
            tbl.appendChild(tr);
          });
          dataArea.appendChild(tbl);

          // EDIT - ویرایش رکورد
          tbl.querySelectorAll(".editBtn").forEach((btn) => {
            btn.onclick = () => {
              let tr = btn.parentNode.parentNode;
              let rowid = tr.dataset.rowid; // گرفتن rowid واقعی

              // تبدیل سلول‌ها به input
              tr.querySelectorAll("td").forEach((td, i) => {
                if (i > 0 && i <= tableDataResponse.schema.columns.length) {
                  let val = td.textContent;
                  td.innerHTML = `<input type="text" value="${val}">`;
                }
              });

              btn.textContent = "ذخیره";

              // ذخیره تغییرات
              btn.onclick = () => {
                let inputs = tr.querySelectorAll("input");
                let payload = {};
                tableDataResponse.schema.columns.forEach((c, i) => {
                  payload[c.name] = inputs[i].value;
                });

                // ارسال داده‌های ویرایش شده به سرور با rowid
                fetch("/update/" + table + "/" + rowid, {
                  method: "POST",
                  body: JSON.stringify(payload),
                  headers: { "Content-Type": "application/json" },
                })
                  .then((r) => r.json())
                  .then((res) => {
                    if (res.ok) retrieveTableData(); // بازخوانی داده‌ها
                  });
              };
            };
          });
        });
    });
}

// اضافه کردن ستون جدید به فرم ایجاد جدول
function defineNewColumnToTable() {
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

  // دکمه حذف ستون
  div.querySelector(".removeCol").onclick = () => div.remove();
}

// حذف رکورد با rowid
function deleteRowByRowIndex(table, rowid) {
  fetch("/delete/" + table + "/" + rowid, { method: "DELETE" })
    .then((r) => r.json())
    .then((res) => {
      if (res.ok) retrieveTableData(); // بازخوانی داده‌ها
    });
}
