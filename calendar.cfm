<cfcontent type="text/html; charset=UTF-8">
<cfquery name="calItems" datasource="reach">
SELECT TOP 100 
       h.ID,
       c.id AS case_id,
       c.case_name AS casename,
       h.hearing_type AS hearingtype,
       h.hearing_type AS title,
       FORMAT(h.hearing_datetime, 'yyyy-MM-ddTHH:mm:ss') AS start,
       'Hearing: ' + h.hearing_type + ' - ' + c.case_name AS description
FROM [docketwatch].[dbo].[hearings] h
INNER JOIN docketwatch.dbo.cases c ON c.id = h.fk_case
 WHERE h.id > 79625
ORDER BY h.hearing_datetime DESC;
</cfquery> 

<!DOCTYPE html>
<html lang="en">
<head>
 <meta charset="UTF-8"> 
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DocketWatch - Hearings Calendar</title>
  <cfinclude template="head.cfm">
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.9/index.global.min.js"></script>
<link href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.9/index.global.min.css" rel="stylesheet" />

<style>
/* SharePoint-like styling for FullCalendar with forced overrides */

.fc {
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif !important;
  font-size: 13px !important;
  color: #333 !important;
}

.fc-toolbar {
  background-color: #f4f4f4 !important;
  border: 1px solid #dcdcdc !important;
  padding: 6px 12px !important;
  margin-bottom: 10px !important;
}

.fc-toolbar-title {
  font-weight: bold !important;
  font-size: 18px !important;
  color: #0072c6 !important;
}

.fc-button {
  background-color: #e5e5e5 !important;
  border: 1px solid #ccc !important;
  color: #333 !important;
  padding: 4px 10px !important;
  margin: 2px !important;
}

.fc-button:hover {
  background-color: #dcdcdc !important;
}

.fc-button-active {
  background-color: #0072c6 !important;
  color: #fff !important;
}

.fc-daygrid-day-number {
  color: #0072c6 !important;
  font-weight: bold !important;
}

.fc-event {
  background-color: #d65e85 !important;
  color: #fff !important;
  border: none !important;
  padding: 2px 4px !important;
  font-size: 12px !important;
  border-radius: 0 !important;
}

.fc-event:hover {
  background-color: #c04e72 !important;
  color: #fff !important;
  cursor: pointer !important;
}
</style>


</head>
<body>

<cfinclude template="navbar.cfm">

<div class="container mt-4">
  <div id="calendar"></div>
</div>

<script>
  document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
      initialView: 'dayGridMonth',
      height: 'auto',
      fixedWeekCount: false,
      showNonCurrentDates: false,
      dayMaxEvents: true,
      headerToolbar: {
        left: 'prev,next today',
        center: 'title',
        right: 'dayGridMonth,timeGridWeek,listWeek'
      },
      eventDisplay: 'block',
      displayEventTime: true,
      events: [
        <cfoutput query="calItems">
          {
            id: #id#,
            title: "#JSStringFormat(calItems.title)#",
            start: "#start#",
            url: "case_details.cfm?id=#case_id#&tab=hearings",
            extendedProps: {
              description: "#JSStringFormat(calItems.description)#",
              caseName: "#JSStringFormat(calItems.casename)#",
              hearingType: "#JSStringFormat(calItems.hearingtype)#"
            }
          }<cfif currentrow LT recordcount>,</cfif>
        </cfoutput>
      ],
      eventClick: function (info) {
        info.jsEvent.preventDefault();
        if (info.event.url) {
          window.open(info.event.url, '_blank');
        }
      },
      eventDidMount: function (info) {
        info.el.title = info.event.extendedProps.description;
        info.el.style.backgroundColor = '#dbeef3';
        info.el.style.border = '1px solid #8db2c6';
        info.el.style.color = '#000';
        info.el.style.borderRadius = '0px';
        info.el.style.padding = '2px 4px';
        info.el.style.fontSize = '12px';
        info.el.style.fontWeight = 'normal';
      },
      dayCellDidMount: function (info) {
        info.el.style.backgroundColor = '#f9f9f9';
        info.el.style.borderColor = '#dcdcdc';
      }
    });
    calendar.render();
  });
</script>


<cfinclude template="footer_script.cfm">

</body>
</html>
