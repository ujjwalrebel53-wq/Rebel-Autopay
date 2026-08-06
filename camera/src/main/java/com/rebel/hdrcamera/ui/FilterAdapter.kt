package com.rebel.hdrcamera.ui

import android.content.res.ColorStateList
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.rebel.hdrcamera.R
import com.rebel.hdrcamera.filters.CameraFilter

class FilterAdapter(
    private val filters: List<CameraFilter>,
    private val onSelected: (Int) -> Unit
) : RecyclerView.Adapter<FilterAdapter.Holder>() {

    var selectedIndex = 0
        private set

    fun select(index: Int) {
        if (index == selectedIndex || index !in filters.indices) return
        val old = selectedIndex
        selectedIndex = index
        notifyItemChanged(old)
        notifyItemChanged(index)
    }

    class Holder(view: View) : RecyclerView.ViewHolder(view) {
        val swatch: FrameLayout = view.findViewById(R.id.swatch)
        val ring: View = view.findViewById(R.id.selectionRing)
        val label: TextView = view.findViewById(R.id.filterName)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_filter, parent, false)
        return Holder(view)
    }

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val filter = filters[position]
        holder.label.text = filter.name
        holder.swatch.backgroundTintList = ColorStateList.valueOf(filter.swatch)
        val selected = position == selectedIndex
        holder.ring.visibility = if (selected) View.VISIBLE else View.INVISIBLE
        holder.label.alpha = if (selected) 1f else 0.7f
        holder.itemView.setOnClickListener {
            val pos = holder.bindingAdapterPosition
            if (pos != RecyclerView.NO_POSITION) onSelected(pos)
        }
    }

    override fun getItemCount(): Int = filters.size
}
