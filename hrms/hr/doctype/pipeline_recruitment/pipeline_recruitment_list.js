frappe.listview_settings["Pipeline Recruitment"] = {
  add_fields: ["status"],
  get_indicator: function (doc) {
    const status_colors = {
      "Open": "blue",
      "Reach out": "cyan",
      "Phone Interview": "purple",
      "Call Not Answered": "orange",
      "Psychological Test": "yellow",
      "HR Interview": "teal",
      "Technical Test": "gray",
      "User Interview": "light-blue",
      "Need Decision": "orange",
      "Rejected": "red",
      "Offer Accepted (Hired)": "green",
      "Applicant Withdrawal": "darkgrey",
      "Talentpool": "purple",
      "Not available": "darkgray",
      "Offering Declined": "red",
      "No Response After Reach Out": "orange",
      "Blacklist": "darkgrey",
      "Hold": "purple"
    };
    const color = status_colors[doc.status] || "gray";
    return [__(doc.status), color, "status,=," + doc.status];
  },
};